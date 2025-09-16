"""
Order Management Service for FXML4 API.

This service manages the complete order lifecycle from signal generation to execution,
integrating with broker adapters and risk management systems.
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

import asyncpg
from pydantic import BaseModel, Field

from fxml4.api.services.market_data import market_data_service
from fxml4.api.services.signal_processing import SignalData, signal_processing_service
from fxml4.brokers.adapters.base import ConnectionStatus, OrderStatus

logger = logging.getLogger(__name__)


class OrderType(str, Enum):
    """Order types supported by the system."""

    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class OrderSide(str, Enum):
    """Order side - buy or sell."""

    BUY = "buy"
    SELL = "sell"


class TimeInForce(str, Enum):
    """Time in force for orders."""

    DAY = "day"
    GTC = "gtc"  # Good Till Cancelled
    IOC = "ioc"  # Immediate or Cancel
    FOK = "fok"  # Fill or Kill


class OrderData(BaseModel):
    """Order data model for internal processing."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: TimeInForce = TimeInForce.DAY
    status: str = "pending"

    # Execution details
    filled_quantity: float = 0.0
    remaining_quantity: Optional[float] = None
    avg_fill_price: Optional[float] = None

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    submitted_at: Optional[datetime] = None
    filled_at: Optional[datetime] = None

    # Signal and strategy context
    signal_id: Optional[str] = None
    strategy_name: Optional[str] = None

    # Risk and compliance
    risk_approved: bool = False
    compliance_checked: bool = False

    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)


class OrderExecution(BaseModel):
    """Order execution event data."""

    execution_id: str
    order_id: str
    symbol: str
    side: OrderSide
    quantity: float
    price: float
    timestamp: datetime
    commission: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class OrderManagementService:
    """Service for managing orders and their lifecycle."""

    def __init__(self):
        self.active_orders: Dict[str, OrderData] = {}
        self.order_history: List[OrderData] = []
        self.executions: Dict[str, List[OrderExecution]] = {}  # order_id -> executions

        # Event callbacks
        self.order_update_callbacks: List[Callable[[OrderData], None]] = []
        self.execution_callbacks: List[Callable[[OrderExecution], None]] = []

        # Services and connections
        self._pool = None
        self.broker_adapters: Dict[str, Any] = {}  # broker_name -> adapter instance

        # Configuration
        self.default_broker = "manual"  # Default to manual execution
        self.auto_execute_signals = False  # Manual approval required by default

    async def initialize(self):
        """Initialize the order management service."""
        try:
            logger.info("Initializing Order Management Service...")

            # Get database connection pool
            self._pool = await market_data_service.get_connection_pool()

            # Initialize broker adapters (start with manual adapter)
            await self._initialize_broker_adapters()

            # Load active orders from database
            await self._load_active_orders()

            logger.info("Order Management Service initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize Order Management Service: {e}")
            raise

    async def _initialize_broker_adapters(self):
        """Initialize available broker adapters."""
        try:
            # Start with manual adapter (always available)
            self.broker_adapters["manual"] = "manual_adapter_placeholder"
            logger.info("Initialized manual broker adapter")

            # Try to initialize other adapters if available
            # This is where we'd connect to IB, FXCM, etc.
            # For now, we'll use manual execution

        except Exception as e:
            logger.error(f"Error initializing broker adapters: {e}")

    async def _load_active_orders(self):
        """Load active orders from database."""
        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT o.*, s.name as symbol_name
                    FROM orders o
                    JOIN symbols s ON o.symbol_id = s.id
                    WHERE o.status IN ('pending', 'submitted', 'acknowledged', 'working', 'partially_filled')
                    ORDER BY o.created_at DESC
                """
                )

                loaded_count = 0
                for row in rows:
                    try:
                        # Convert database row to OrderData
                        order = self._db_row_to_order(row)
                        self.active_orders[order.id] = order
                        loaded_count += 1
                    except Exception as e:
                        logger.error(
                            f"Error loading order {row.get('id', 'unknown')}: {e}"
                        )

                logger.info(f"Loaded {loaded_count} active orders from database")

        except Exception as e:
            logger.error(f"Error loading active orders: {e}")

    def _db_row_to_order(self, row) -> OrderData:
        """Convert database row to OrderData object."""
        # Map proper orders table fields to OrderData
        side = OrderSide.BUY if row.get("side") == "buy" else OrderSide.SELL

        # Map order type from database
        order_type_map = {
            "market": OrderType.MARKET,
            "limit": OrderType.LIMIT,
            "stop": OrderType.STOP,
            "stop_limit": OrderType.STOP_LIMIT,
        }
        order_type = order_type_map.get(
            row.get("order_type", "market"), OrderType.MARKET
        )

        return OrderData(
            id=str(row["id"]),
            symbol=row["symbol_name"],
            side=side,
            order_type=order_type,
            quantity=abs(float(row.get("quantity", 0))),
            price=float(row.get("price")) if row.get("price") else None,
            status=row.get("status", "pending"),
            created_at=row.get("created_at", datetime.utcnow()),
            filled_quantity=(
                float(row.get("filled_quantity", 0))
                if row.get("filled_quantity")
                else 0.0
            ),
            avg_fill_price=(
                float(row.get("average_fill_price"))
                if row.get("average_fill_price")
                else None
            ),
            metadata=(
                json.loads(row.get("metadata", "{}")) if row.get("metadata") else {}
            ),
        )

    async def create_order_from_signal(
        self,
        signal: SignalData,
        quantity: float,
        order_type: OrderType = OrderType.MARKET,
        price: Optional[float] = None,
        auto_execute: bool = False,
    ) -> OrderData:
        """Create an order from a trading signal."""
        try:
            # Determine order side from signal direction
            if signal.direction > 0:
                side = OrderSide.BUY
            elif signal.direction < 0:
                side = OrderSide.SELL
            else:
                raise ValueError(
                    "Signal direction is neutral (0) - cannot create order"
                )

            # Create order
            order = OrderData(
                symbol=signal.symbol,
                side=side,
                order_type=order_type,
                quantity=abs(quantity),
                price=price,
                signal_id=signal.symbol + "_" + signal.timestamp.isoformat(),
                strategy_name=signal.signal_type,
                metadata={
                    "signal_confidence": signal.confidence,
                    "signal_source": signal.source,
                    "signal_metadata": signal.metadata,
                    "created_from": "signal",
                },
            )

            # Risk and compliance checks
            await self._perform_risk_checks(order)
            await self._perform_compliance_checks(order)

            # Store in active orders
            self.active_orders[order.id] = order

            # Store in database
            await self._store_order(order)

            # Execute if auto-execute is enabled and checks passed
            if auto_execute and order.risk_approved and order.compliance_checked:
                await self.execute_order(order.id)

            logger.info(
                f"Created order {order.id} from signal: {side.value} {quantity} {signal.symbol}"
            )

            # Notify callbacks
            await self._notify_order_update(order)

            return order

        except Exception as e:
            logger.error(f"Error creating order from signal: {e}")
            raise

    async def create_manual_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: float,
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
        time_in_force: TimeInForce = TimeInForce.DAY,
    ) -> OrderData:
        """Create a manual order."""
        try:
            order = OrderData(
                symbol=symbol,
                side=side,
                order_type=order_type,
                quantity=quantity,
                price=price,
                stop_price=stop_price,
                time_in_force=time_in_force,
                metadata={"created_from": "manual"},
            )

            # Risk and compliance checks
            await self._perform_risk_checks(order)
            await self._perform_compliance_checks(order)

            # Store in active orders
            self.active_orders[order.id] = order

            # Store in database
            await self._store_order(order)

            logger.info(
                f"Created manual order {order.id}: {side.value} {quantity} {symbol}"
            )

            # Notify callbacks
            await self._notify_order_update(order)

            return order

        except Exception as e:
            logger.error(f"Error creating manual order: {e}")
            raise

    async def _perform_risk_checks(self, order: OrderData) -> bool:
        """Perform risk management checks on order."""
        try:
            # Basic risk checks
            risk_approved = True

            # Check position size limits
            current_exposure = await self._get_symbol_exposure(order.symbol)
            max_exposure = 100000  # Default max exposure per symbol

            if (
                abs(
                    current_exposure
                    + (order.quantity * (1 if order.side == OrderSide.BUY else -1))
                )
                > max_exposure
            ):
                risk_approved = False
                logger.warning(
                    f"Order {order.id} rejected: exceeds position limit for {order.symbol}"
                )

            # Check order size limits
            max_order_size = 50000  # Default max order size
            if order.quantity > max_order_size:
                risk_approved = False
                logger.warning(f"Order {order.id} rejected: exceeds order size limit")

            # Check account balance (simplified)
            # In production, this would check actual account equity

            order.risk_approved = risk_approved
            order.metadata["risk_checks"] = {
                "approved": risk_approved,
                "current_exposure": current_exposure,
                "check_timestamp": datetime.utcnow().isoformat(),
            }

            return risk_approved

        except Exception as e:
            logger.error(f"Error in risk checks for order {order.id}: {e}")
            order.risk_approved = False
            return False

    async def _perform_compliance_checks(self, order: OrderData) -> bool:
        """Perform compliance checks on order."""
        try:
            # Basic compliance checks
            compliance_approved = True

            # Check trading hours (simplified)
            current_hour = datetime.utcnow().hour
            if not (0 <= current_hour <= 23):  # 24/7 for forex
                compliance_approved = True  # Forex trades 24/5

            # Check symbol is tradeable
            available_symbols = await market_data_service.get_available_symbols()
            if order.symbol not in available_symbols:
                compliance_approved = False
                logger.warning(
                    f"Order {order.id} rejected: symbol {order.symbol} not available"
                )

            order.compliance_checked = True
            order.metadata["compliance_checks"] = {
                "approved": compliance_approved,
                "check_timestamp": datetime.utcnow().isoformat(),
            }

            return compliance_approved

        except Exception as e:
            logger.error(f"Error in compliance checks for order {order.id}: {e}")
            order.compliance_checked = False
            return False

    async def _get_symbol_exposure(self, symbol: str) -> float:
        """Get current exposure for a symbol."""
        try:
            exposure = 0.0
            for order in self.active_orders.values():
                if order.symbol == symbol and order.status in [
                    "filled",
                    "partially_filled",
                ]:
                    if order.side == OrderSide.BUY:
                        exposure += order.filled_quantity
                    else:
                        exposure -= order.filled_quantity
            return exposure
        except Exception as e:
            logger.error(f"Error calculating exposure for {symbol}: {e}")
            return 0.0

    async def execute_order(self, order_id: str, broker: Optional[str] = None) -> bool:
        """Execute an order through the specified broker."""
        try:
            if order_id not in self.active_orders:
                raise ValueError(f"Order {order_id} not found")

            order = self.active_orders[order_id]

            # Check if order can be executed
            if not (order.risk_approved and order.compliance_checked):
                raise ValueError(f"Order {order_id} not approved for execution")

            if order.status not in ["pending"]:
                raise ValueError(
                    f"Order {order_id} cannot be executed in status {order.status}"
                )

            # Use specified broker or default
            broker_name = broker or self.default_broker

            if broker_name not in self.broker_adapters:
                raise ValueError(f"Broker {broker_name} not available")

            # Update order status
            order.status = "submitted"
            order.submitted_at = datetime.utcnow()

            # For manual execution, simulate immediate fill for testing
            if broker_name == "manual":
                success = await self._simulate_manual_execution(order)
            else:
                # Execute through broker adapter
                success = await self._execute_through_broker(order, broker_name)

            # Update database
            await self._update_order_status(order)

            # Notify callbacks
            await self._notify_order_update(order)

            logger.info(f"Order {order_id} executed successfully via {broker_name}")
            return success

        except Exception as e:
            logger.error(f"Error executing order {order_id}: {e}")

            # Update order status to error
            if order_id in self.active_orders:
                self.active_orders[order_id].status = "rejected"
                self.active_orders[order_id].metadata["error"] = str(e)
                await self._update_order_status(self.active_orders[order_id])

            return False

    async def _simulate_manual_execution(self, order: OrderData) -> bool:
        """Simulate manual order execution for testing."""
        try:
            # Get current market price
            tick_data = await market_data_service.get_latest_tick(order.symbol)

            if not tick_data:
                # Use a default price if no tick data available
                execution_price = order.price if order.price else 1.1000
            else:
                execution_price = tick_data["price"]

            # Create execution
            execution = OrderExecution(
                execution_id=str(uuid.uuid4()),
                order_id=order.id,
                symbol=order.symbol,
                side=order.side,
                quantity=order.quantity,
                price=execution_price,
                timestamp=datetime.utcnow(),
                metadata={"broker": "manual", "simulated": True},
            )

            # Update order
            order.status = "filled"
            order.filled_quantity = order.quantity
            order.avg_fill_price = execution_price
            order.filled_at = datetime.utcnow()
            order.remaining_quantity = 0.0

            # Store execution
            if order.id not in self.executions:
                self.executions[order.id] = []
            self.executions[order.id].append(execution)

            # Store execution in database
            await self._store_execution(execution)

            # Notify execution callbacks
            await self._notify_execution(execution)

            logger.info(
                f"Simulated execution: {order.side.value} {order.quantity} {order.symbol} @ {execution_price}"
            )
            return True

        except Exception as e:
            logger.error(f"Error in manual execution simulation: {e}")
            return False

    async def _execute_through_broker(self, order: OrderData, broker_name: str) -> bool:
        """Execute order through a real broker adapter."""
        try:
            # This would integrate with actual broker adapters
            # For now, return False to indicate not implemented
            logger.warning(f"Real broker execution not implemented for {broker_name}")
            return False

        except Exception as e:
            logger.error(f"Error executing through {broker_name}: {e}")
            return False

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an active order."""
        try:
            if order_id not in self.active_orders:
                raise ValueError(f"Order {order_id} not found")

            order = self.active_orders[order_id]

            if order.status not in ["pending", "submitted", "acknowledged", "working"]:
                raise ValueError(f"Cannot cancel order in status {order.status}")

            # Update status
            order.status = "cancelled"
            order.metadata["cancelled_at"] = datetime.utcnow().isoformat()

            # Move to history
            self.order_history.append(order)
            del self.active_orders[order_id]

            # Update database
            await self._update_order_status(order)

            # Notify callbacks
            await self._notify_order_update(order)

            logger.info(f"Cancelled order {order_id}")
            return True

        except Exception as e:
            logger.error(f"Error cancelling order {order_id}: {e}")
            return False

    async def get_order(self, order_id: str) -> Optional[OrderData]:
        """Get order by ID."""
        return self.active_orders.get(order_id)

    async def get_orders(
        self,
        symbol: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[OrderData]:
        """Get orders with optional filtering."""
        orders = list(self.active_orders.values())

        if symbol:
            orders = [o for o in orders if o.symbol == symbol]

        if status:
            orders = [o for o in orders if o.status == status]

        # Sort by creation time, most recent first
        orders.sort(key=lambda x: x.created_at, reverse=True)

        return orders[:limit]

    async def get_executions(self, order_id: str) -> List[OrderExecution]:
        """Get executions for an order."""
        return self.executions.get(order_id, [])

    async def _store_order(self, order: OrderData):
        """Store order in database."""
        try:
            async with self._pool.acquire() as conn:
                # Store in backtest_trades table for now
                # In production, you'd have a dedicated orders table
                await conn.execute(
                    """
                    INSERT INTO backtest_trades (
                        id, symbol_id, entry_timestamp, direction, entry_price,
                        quantity, status, metadata
                    ) VALUES (
                        $1,
                        (SELECT id FROM symbols WHERE name = $2 LIMIT 1),
                        $3, $4, $5, $6, $7, $8
                    ) ON CONFLICT (id) DO UPDATE SET
                        status = EXCLUDED.status,
                        metadata = EXCLUDED.metadata
                """,
                    uuid.UUID(order.id),
                    order.symbol,
                    order.created_at,
                    order.side.value,
                    order.price,
                    order.quantity,
                    order.status,
                    json.dumps(order.metadata),
                )
        except Exception as e:
            logger.error(f"Error storing order {order.id}: {e}")

    async def _update_order_status(self, order: OrderData):
        """Update order status in database."""
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE backtest_trades SET
                        status = $1,
                        exit_price = $2,
                        filled_qty = $3,
                        metadata = $4
                    WHERE id = $5
                """,
                    order.status,
                    order.avg_fill_price,
                    order.filled_quantity,
                    json.dumps(order.metadata),
                    uuid.UUID(order.id),
                )
        except Exception as e:
            logger.error(f"Error updating order {order.id}: {e}")

    async def _store_execution(self, execution: OrderExecution):
        """Store execution in database."""
        try:
            # In production, you'd have an executions table
            # For now, just log the execution
            logger.info(f"Execution stored: {execution.execution_id}")
        except Exception as e:
            logger.error(f"Error storing execution {execution.execution_id}: {e}")

    async def _notify_order_update(self, order: OrderData):
        """Notify all order update callbacks."""
        try:
            for callback in self.order_update_callbacks:
                try:
                    callback(order)
                except Exception as e:
                    logger.error(f"Error in order update callback: {e}")

            # Broadcast via WebSocket
            await self._broadcast_order_update(order)

        except Exception as e:
            logger.error(f"Error notifying order update: {e}")

    async def _notify_execution(self, execution: OrderExecution):
        """Notify all execution callbacks."""
        try:
            for callback in self.execution_callbacks:
                try:
                    callback(execution)
                except Exception as e:
                    logger.error(f"Error in execution callback: {e}")

            # Broadcast via WebSocket
            await self._broadcast_execution(execution)

        except Exception as e:
            logger.error(f"Error notifying execution: {e}")

    async def _broadcast_order_update(self, order: OrderData):
        """Broadcast order update via WebSocket."""
        try:
            from fxml4.api.services.websocket import websocket_service

            message = {
                "type": "order_update",
                "order": {
                    "id": order.id,
                    "symbol": order.symbol,
                    "side": order.side.value,
                    "order_type": order.order_type.value,
                    "quantity": order.quantity,
                    "price": order.price,
                    "status": order.status,
                    "filled_quantity": order.filled_quantity,
                    "avg_fill_price": order.avg_fill_price,
                    "created_at": order.created_at.isoformat(),
                    "metadata": order.metadata,
                },
                "timestamp": datetime.utcnow().isoformat(),
            }

            # Broadcast to order subscribers
            await websocket_service.manager.broadcast_to_subscribers(
                f"orders:{order.symbol}", message
            )
            await websocket_service.manager.broadcast_to_subscribers(
                "orders:all", message
            )

        except Exception as e:
            logger.error(f"Error broadcasting order update: {e}")

    async def _broadcast_execution(self, execution: OrderExecution):
        """Broadcast execution via WebSocket."""
        try:
            from fxml4.api.services.websocket import websocket_service

            message = {
                "type": "execution",
                "execution": {
                    "execution_id": execution.execution_id,
                    "order_id": execution.order_id,
                    "symbol": execution.symbol,
                    "side": execution.side.value,
                    "quantity": execution.quantity,
                    "price": execution.price,
                    "timestamp": execution.timestamp.isoformat(),
                    "commission": execution.commission,
                    "metadata": execution.metadata,
                },
                "timestamp": datetime.utcnow().isoformat(),
            }

            # Broadcast to execution subscribers
            await websocket_service.manager.broadcast_to_subscribers(
                f"executions:{execution.symbol}", message
            )
            await websocket_service.manager.broadcast_to_subscribers(
                "executions:all", message
            )

        except Exception as e:
            logger.error(f"Error broadcasting execution: {e}")

    def add_order_update_callback(self, callback: Callable[[OrderData], None]):
        """Add callback for order updates."""
        self.order_update_callbacks.append(callback)

    def add_execution_callback(self, callback: Callable[[OrderExecution], None]):
        """Add callback for executions."""
        self.execution_callbacks.append(callback)

    async def close(self):
        """Close the order management service."""
        try:
            logger.info("Closing Order Management Service...")

            # Cancel all pending orders (optional)
            # pending_orders = [o for o in self.active_orders.values() if o.status == "pending"]
            # for order in pending_orders:
            #     await self.cancel_order(order.id)

            logger.info("Order Management Service closed")

        except Exception as e:
            logger.error(f"Error closing Order Management Service: {e}")


# Global service instance
order_management_service = OrderManagementService()
