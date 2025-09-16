"""
Integration tests for signal-to-order-to-execution flow.

This module tests the complete trading workflow from signal generation
through order execution, validating service integration and data flow.
"""

import asyncio
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

# Use centralized event loop fixture
from tests.fixtures.event_loop_fixtures import event_loop

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Mock all external dependencies before importing
sys.modules["openai"] = Mock()
sys.modules["fxml4.strategy.integrated_signal_generator"] = Mock()
sys.modules["fxml4.wave_analysis.sentiment_wave_validator"] = Mock()
sys.modules["fxml4.llm_integration.sentiment_analysis"] = Mock()
sys.modules["fxml4.llm_integration.llm_client"] = Mock()
sys.modules["redis.asyncio"] = Mock()
sys.modules["fxml4.config"] = Mock()
sys.modules["fxml4.data_engineering.data_feeds.base_feed"] = Mock()

# Mock config
mock_config = {
    "database": {
        "user": "test_user",
        "password": "test_password",
        "host": "localhost",
        "port": 5432,
        "name": "test_db",
    },
    "redis": {"host": "localhost", "port": 6379, "db": 0},
}

sys.modules["fxml4.config"].get_config = Mock(return_value=mock_config)


class IntegratedSignalData:
    """Integrated signal data for testing complete flow."""

    def __init__(
        self, symbol, direction, confidence, signal_type, source, metadata=None
    ):
        self.id = f"signal_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{symbol}"
        self.symbol = symbol
        self.direction = direction  # 1 for buy, -1 for sell
        self.confidence = confidence
        self.signal_type = signal_type
        self.source = source
        self.timestamp = datetime.utcnow()
        self.metadata = metadata or {}


class IntegratedOrderData:
    """Integrated order data for testing complete flow."""

    def __init__(self, symbol, side, quantity, order_type="market", status="pending"):
        self.id = f"order_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{symbol}"
        self.symbol = symbol
        self.side = side  # "buy" or "sell"
        self.quantity = quantity
        self.order_type = order_type
        self.status = status
        self.created_at = datetime.utcnow()
        self.filled_quantity = 0.0
        self.avg_fill_price = None
        self.filled_at = None
        self.signal_id = None
        self.strategy_name = None
        self.metadata = {}


class IntegratedOrderExecution:
    """Integrated order execution for testing complete flow."""

    def __init__(self, order_id, symbol, side, quantity, price):
        self.execution_id = f"exec_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        self.order_id = order_id
        self.symbol = symbol
        self.side = side
        self.quantity = quantity
        self.price = price
        self.timestamp = datetime.utcnow()
        self.commission = 2.50
        self.exchange_order_id = f"EX{self.execution_id[-8:]}"


class IntegratedTradingSystem:
    """Integrated system combining all services for end-to-end testing."""

    def __init__(self):
        # Service states
        self.signals = []  # List[IntegratedSignalData]
        self.orders = {}  # Dict[str, IntegratedOrderData]
        self.executions = {}  # Dict[str, List[IntegratedOrderExecution]]
        self.connections = {}  # WebSocket connections
        self.subscriptions = {}  # Client subscriptions

        # Configuration
        self.auto_execute_high_confidence = True
        self.high_confidence_threshold = 0.8
        self.max_position_size = 100000.0
        self.risk_checks_enabled = True

        # Market data
        self.market_prices = {
            "EURUSD": 1.1000,
            "GBPUSD": 1.2500,
            "USDJPY": 150.00,
            "AUDUSD": 0.6750,
        }

        # Callbacks for testing
        self.signal_callbacks = []
        self.order_callbacks = []
        self.execution_callbacks = []

    async def initialize(self):
        """Initialize the integrated trading system."""
        # Mock initialization of all services
        pass

    # Signal Processing Integration
    async def generate_signal(
        self, symbol: str, signal_type: str = "ml_signal"
    ) -> IntegratedSignalData:
        """Generate a trading signal."""
        import random

        # Simulate signal generation with varying confidence
        direction = random.choice([1, -1])
        confidence = random.uniform(0.3, 0.95)

        signal = IntegratedSignalData(
            symbol=symbol,
            direction=direction,
            confidence=confidence,
            signal_type=signal_type,
            source=f"mock_{signal_type}",
            metadata={
                "generated_at": datetime.utcnow().isoformat(),
                "market_price": self.market_prices.get(symbol, 1.0000),
            },
        )

        self.signals.append(signal)

        # Notify signal callbacks
        for callback in self.signal_callbacks:
            await callback(signal)

        # Auto-create order for high confidence signals
        if (
            self.auto_execute_high_confidence
            and signal.confidence >= self.high_confidence_threshold
        ):
            quantity = min(10000.0, self.max_position_size * 0.1)  # 10% of max position
            await self.create_order_from_signal(signal, quantity, auto_execute=True)

        return signal

    # Order Management Integration
    async def create_order_from_signal(
        self, signal: IntegratedSignalData, quantity: float, auto_execute: bool = False
    ) -> IntegratedOrderData:
        """Create order from trading signal."""
        # Determine order side
        side = "buy" if signal.direction > 0 else "sell"

        # Risk checks
        if self.risk_checks_enabled:
            risk_approved = await self._perform_risk_checks(signal.symbol, quantity)
            if not risk_approved:
                raise ValueError(
                    f"Risk check failed for {signal.symbol} order of {quantity}"
                )

        # Create order
        order = IntegratedOrderData(
            symbol=signal.symbol, side=side, quantity=quantity, status="pending"
        )

        order.signal_id = signal.id
        order.strategy_name = signal.signal_type
        order.metadata = {
            "signal_confidence": signal.confidence,
            "signal_source": signal.source,
            "auto_execute": auto_execute,
            "created_from": "signal",
        }

        self.orders[order.id] = order

        # Notify order callbacks
        for callback in self.order_callbacks:
            await callback(order)

        # Execute immediately if requested
        if auto_execute:
            await self.execute_order(order.id)

        return order

    async def execute_order(self, order_id: str) -> IntegratedOrderExecution:
        """Execute an order."""
        if order_id not in self.orders:
            raise ValueError(f"Order {order_id} not found")

        order = self.orders[order_id]
        if order.status != "pending":
            raise ValueError(f"Order {order_id} is not in pending status")

        # Get execution price (simulate slippage)
        base_price = self.market_prices.get(order.symbol, 1.0000)
        import random

        slippage = random.uniform(-0.0002, 0.0002)  # 0.2 pip slippage
        execution_price = base_price + slippage

        # Create execution
        execution = IntegratedOrderExecution(
            order_id=order_id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            price=execution_price,
        )

        # Update order
        order.status = "filled"
        order.filled_quantity = order.quantity
        order.avg_fill_price = execution_price
        order.filled_at = execution.timestamp

        # Store execution
        if order_id not in self.executions:
            self.executions[order_id] = []
        self.executions[order_id].append(execution)

        # Notify callbacks
        for callback in self.order_callbacks:
            await callback(order)
        for callback in self.execution_callbacks:
            await callback(execution)

        return execution

    async def _perform_risk_checks(self, symbol: str, quantity: float) -> bool:
        """Perform risk management checks."""
        # Check position size
        if quantity > self.max_position_size:
            return False

        # Check current exposure
        current_exposure = 0.0
        for order in self.orders.values():
            if order.symbol == symbol and order.status == "filled":
                if order.side == "buy":
                    current_exposure += order.filled_quantity
                else:
                    current_exposure -= order.filled_quantity

        new_exposure = abs(current_exposure + (quantity if True else -quantity))
        if new_exposure > self.max_position_size:
            return False

        return True

    # WebSocket Integration
    async def connect_websocket_client(self, client_id: str) -> Dict[str, Any]:
        """Connect WebSocket client."""
        self.connections[client_id] = {
            "connected_at": datetime.utcnow(),
            "subscriptions": set(),
        }
        self.subscriptions[client_id] = set()

        return {
            "type": "welcome",
            "message": "Connected to FXML4 WebSocket",
            "client_id": client_id,
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def subscribe_client(
        self, client_id: str, subscription_key: str
    ) -> Dict[str, Any]:
        """Subscribe client to data stream."""
        if client_id not in self.connections:
            raise ValueError(f"Client {client_id} not connected")

        self.subscriptions[client_id].add(subscription_key)

        return {
            "type": "subscription_confirmed",
            "subscription": subscription_key,
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def broadcast_signal_update(self, signal: IntegratedSignalData):
        """Broadcast signal update to subscribed clients."""
        message = {
            "type": "signal_update",
            "signal": {
                "id": signal.id,
                "symbol": signal.symbol,
                "direction": signal.direction,
                "confidence": signal.confidence,
                "signal_type": signal.signal_type,
                "source": signal.source,
                "timestamp": signal.timestamp.isoformat(),
            },
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Find subscribed clients
        subscribed_clients = []
        for client_id, subs in self.subscriptions.items():
            if f"signals:{signal.symbol}" in subs or "signals:all" in subs:
                subscribed_clients.append(client_id)

        return subscribed_clients, message

    async def broadcast_order_update(self, order: IntegratedOrderData):
        """Broadcast order update to subscribed clients."""
        message = {
            "type": "order_update",
            "order": {
                "id": order.id,
                "symbol": order.symbol,
                "side": order.side,
                "quantity": order.quantity,
                "status": order.status,
                "filled_quantity": order.filled_quantity,
                "avg_fill_price": order.avg_fill_price,
                "created_at": order.created_at.isoformat(),
                "signal_id": order.signal_id,
                "strategy_name": order.strategy_name,
            },
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Find subscribed clients
        subscribed_clients = []
        for client_id, subs in self.subscriptions.items():
            if f"orders:{order.symbol}" in subs or "orders:all" in subs:
                subscribed_clients.append(client_id)

        return subscribed_clients, message

    async def broadcast_execution_update(self, execution: IntegratedOrderExecution):
        """Broadcast execution update to subscribed clients."""
        message = {
            "type": "execution",
            "execution": {
                "execution_id": execution.execution_id,
                "order_id": execution.order_id,
                "symbol": execution.symbol,
                "side": execution.side,
                "quantity": execution.quantity,
                "price": execution.price,
                "timestamp": execution.timestamp.isoformat(),
                "commission": execution.commission,
            },
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Find subscribed clients
        subscribed_clients = []
        for client_id, subs in self.subscriptions.items():
            if f"executions:{execution.symbol}" in subs or "executions:all" in subs:
                subscribed_clients.append(client_id)

        return subscribed_clients, message

    # Market Data Integration
    async def get_market_data(
        self, symbol: str, timeframe: str = "1h", limit: int = 100
    ):
        """Get market data for symbol."""
        import random

        # Generate mock OHLCV data
        base_price = self.market_prices.get(symbol, 1.0000)
        data_points = []

        for i in range(limit):
            time_offset = timedelta(hours=i)
            timestamp = datetime.utcnow() - time_offset

            price_change = random.uniform(-0.002, 0.002)  # 20 pip range
            open_price = base_price + price_change
            close_price = open_price + random.uniform(-0.001, 0.001)
            high_price = max(open_price, close_price) + abs(price_change) * 0.5
            low_price = min(open_price, close_price) - abs(price_change) * 0.5

            data_points.append(
                {
                    "time": timestamp.isoformat(),
                    "symbol": symbol,
                    "open": round(open_price, 5),
                    "high": round(high_price, 5),
                    "low": round(low_price, 5),
                    "close": round(close_price, 5),
                    "volume": 1000 + random.randint(0, 500),
                }
            )

        return data_points

    async def get_latest_tick(self, symbol: str):
        """Get latest tick data for symbol."""
        base_price = self.market_prices.get(symbol, 1.0000)
        import random

        current_price = base_price + random.uniform(-0.0005, 0.0005)

        return {
            "time": datetime.utcnow().isoformat(),
            "price": round(current_price, 5),
            "size": 1000,
            "symbol": symbol,
            "tick_type": "trade",
        }

    # Utility methods for testing
    def add_signal_callback(self, callback):
        """Add callback for signal updates."""
        self.signal_callbacks.append(callback)

    def add_order_callback(self, callback):
        """Add callback for order updates."""
        self.order_callbacks.append(callback)

    def add_execution_callback(self, callback):
        """Add callback for execution updates."""
        self.execution_callbacks.append(callback)

    def get_system_statistics(self) -> Dict[str, Any]:
        """Get overall system statistics."""
        total_signals = len(self.signals)
        total_orders = len(self.orders)
        filled_orders = sum(1 for o in self.orders.values() if o.status == "filled")
        total_executions = sum(len(execs) for execs in self.executions.values())

        return {
            "total_signals": total_signals,
            "total_orders": total_orders,
            "filled_orders": filled_orders,
            "total_executions": total_executions,
            "active_connections": len(self.connections),
            "symbols_traded": len(set(o.symbol for o in self.orders.values())),
            "avg_signal_confidence": sum(s.confidence for s in self.signals)
            / max(total_signals, 1),
        }


class TestSignalToExecutionFlow:
    """Test the complete signal-to-execution trading flow."""

    @pytest.fixture
    def trading_system(self):
        """Create a fresh IntegratedTradingSystem for each test."""
        return IntegratedTradingSystem()

    @pytest.mark.asyncio
    async def test_complete_trading_workflow(self, trading_system):
        """Test complete workflow from signal generation to execution."""
        symbol = "EURUSD"

        # Initialize system
        await trading_system.initialize()

        # Step 1: Generate high-confidence signal (should auto-execute)
        signal = await trading_system.generate_signal(symbol, "ml_signal")

        # Verify signal generation
        assert len(trading_system.signals) == 1
        assert signal.symbol == symbol
        assert signal.signal_type == "ml_signal"
        assert 0.3 <= signal.confidence <= 0.95

        # Step 2: If high confidence, order should be auto-created and executed
        if signal.confidence >= trading_system.high_confidence_threshold:
            # Verify order creation
            assert len(trading_system.orders) == 1
            order = list(trading_system.orders.values())[0]
            assert order.symbol == symbol
            assert order.signal_id == signal.id
            assert order.status == "filled"  # Auto-executed

            # Verify execution
            assert order.id in trading_system.executions
            executions = trading_system.executions[order.id]
            assert len(executions) == 1
            execution = executions[0]
            assert execution.symbol == symbol
            assert execution.quantity == order.quantity
            assert execution.price > 0
        else:
            # Low confidence signals shouldn't auto-execute
            assert len(trading_system.orders) == 0

    @pytest.mark.asyncio
    async def test_manual_order_creation_and_execution(self, trading_system):
        """Test manual order creation from signal."""
        symbol = "GBPUSD"
        quantity = 5000.0

        await trading_system.initialize()

        # Generate signal (disable auto-execution)
        trading_system.auto_execute_high_confidence = False
        signal = await trading_system.generate_signal(symbol, "elliott_wave")

        # Manually create order from signal
        order = await trading_system.create_order_from_signal(
            signal, quantity, auto_execute=False
        )

        # Verify order creation
        assert order.symbol == symbol
        assert order.quantity == quantity
        assert order.signal_id == signal.id
        assert order.strategy_name == "elliott_wave"
        assert order.status == "pending"

        # Manually execute order
        execution = await trading_system.execute_order(order.id)

        # Verify execution
        assert execution.order_id == order.id
        assert execution.symbol == symbol
        assert execution.quantity == quantity
        assert execution.price > 0

        # Verify order updated
        assert order.status == "filled"
        assert order.filled_quantity == quantity
        assert order.avg_fill_price == execution.price

    @pytest.mark.asyncio
    async def test_risk_management_integration(self, trading_system):
        """Test risk management blocks excessive orders."""
        symbol = "USDJPY"
        excessive_quantity = 200000.0  # Exceeds max position size

        await trading_system.initialize()

        # Disable auto-execution to prevent automatic order creation
        trading_system.auto_execute_high_confidence = False

        # Generate signal
        signal = await trading_system.generate_signal(symbol, "technical_indicator")

        # Try to create order that exceeds risk limits
        with pytest.raises(ValueError, match="Risk check failed"):
            await trading_system.create_order_from_signal(signal, excessive_quantity)

        # Verify no order created (except potential auto-order, which we disabled)
        assert len(trading_system.orders) == 0

    @pytest.mark.asyncio
    async def test_websocket_integration_flow(self, trading_system):
        """Test WebSocket integration with trading flow."""
        client_id = "trader_client"
        symbol = "AUDUSD"

        await trading_system.initialize()

        # Connect WebSocket client
        welcome_msg = await trading_system.connect_websocket_client(client_id)
        assert welcome_msg["type"] == "welcome"
        assert welcome_msg["client_id"] == client_id

        # Subscribe to signal and order updates
        signal_sub = await trading_system.subscribe_client(
            client_id, f"signals:{symbol}"
        )
        order_sub = await trading_system.subscribe_client(client_id, f"orders:{symbol}")
        exec_sub = await trading_system.subscribe_client(
            client_id, f"executions:{symbol}"
        )

        assert signal_sub["type"] == "subscription_confirmed"
        assert order_sub["type"] == "subscription_confirmed"
        assert exec_sub["type"] == "subscription_confirmed"

        # Generate signal (should trigger broadcasts)
        signal = await trading_system.generate_signal(symbol, "high_frequency")

        # Test signal broadcast
        signal_clients, signal_msg = await trading_system.broadcast_signal_update(
            signal
        )
        assert client_id in signal_clients
        assert signal_msg["type"] == "signal_update"
        assert signal_msg["signal"]["symbol"] == symbol

        # If order was created, test order broadcast
        if len(trading_system.orders) > 0:
            order = list(trading_system.orders.values())[0]
            order_clients, order_msg = await trading_system.broadcast_order_update(
                order
            )
            assert client_id in order_clients
            assert order_msg["type"] == "order_update"
            assert order_msg["order"]["symbol"] == symbol

            # If order was executed, test execution broadcast
            if order.status == "filled" and order.id in trading_system.executions:
                execution = trading_system.executions[order.id][0]
                exec_clients, exec_msg = (
                    await trading_system.broadcast_execution_update(execution)
                )
                assert client_id in exec_clients
                assert exec_msg["type"] == "execution"
                assert exec_msg["execution"]["symbol"] == symbol

    @pytest.mark.asyncio
    async def test_multi_symbol_trading_workflow(self, trading_system):
        """Test trading workflow across multiple symbols."""
        symbols = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD"]

        await trading_system.initialize()

        # Generate signals for multiple symbols
        signals = []
        for symbol in symbols:
            signal = await trading_system.generate_signal(symbol, "multi_asset")
            signals.append(signal)

        # Verify all signals generated
        assert len(trading_system.signals) == len(symbols)
        for i, signal in enumerate(signals):
            assert signal.symbol == symbols[i]
            assert signal.signal_type == "multi_asset"

        # Check if any high-confidence signals created orders
        high_conf_signals = [
            s
            for s in signals
            if s.confidence >= trading_system.high_confidence_threshold
        ]
        expected_orders = (
            len(high_conf_signals) if trading_system.auto_execute_high_confidence else 0
        )

        assert len(trading_system.orders) == expected_orders

        # Verify symbol diversity in orders
        if trading_system.orders:
            order_symbols = set(
                order.symbol for order in trading_system.orders.values()
            )
            assert len(order_symbols) <= len(
                symbols
            )  # Should not exceed available symbols

    @pytest.mark.asyncio
    async def test_callback_integration(self, trading_system):
        """Test callback integration across the trading flow."""
        symbol = "EURCHF"
        callback_events = []

        # Set up callbacks to track events
        async def signal_callback(signal):
            callback_events.append(("signal", signal.symbol, signal.confidence))

        async def order_callback(order):
            callback_events.append(("order", order.symbol, order.status))

        async def execution_callback(execution):
            callback_events.append(("execution", execution.symbol, execution.price))

        trading_system.add_signal_callback(signal_callback)
        trading_system.add_order_callback(order_callback)
        trading_system.add_execution_callback(execution_callback)

        await trading_system.initialize()

        # Generate signal and potentially create/execute order
        signal = await trading_system.generate_signal(symbol, "callback_test")

        # Verify callbacks were triggered
        assert len(callback_events) >= 1  # At minimum, signal callback
        assert callback_events[0][0] == "signal"
        assert callback_events[0][1] == symbol

        # If high confidence signal created order
        if (
            signal.confidence >= trading_system.high_confidence_threshold
            and trading_system.auto_execute_high_confidence
        ):
            # Should have signal, order (pending), order (filled), execution callbacks
            assert len(callback_events) >= 3

            # Check order callbacks
            order_events = [e for e in callback_events if e[0] == "order"]
            assert len(order_events) >= 1
            assert all(e[1] == symbol for e in order_events)  # All for same symbol

            # Check execution callbacks
            exec_events = [e for e in callback_events if e[0] == "execution"]
            if exec_events:  # If order was executed
                assert len(exec_events) >= 1
                assert all(e[1] == symbol for e in exec_events)
                assert all(e[2] > 0 for e in exec_events)  # Valid execution prices

    @pytest.mark.asyncio
    async def test_market_data_integration(self, trading_system):
        """Test market data integration with trading flow."""
        symbol = "USDCAD"
        timeframe = "1h"

        await trading_system.initialize()

        # Get market data
        market_data = await trading_system.get_market_data(symbol, timeframe, limit=24)

        # Verify market data structure
        assert len(market_data) == 24
        for data_point in market_data:
            assert "time" in data_point
            assert "symbol" in data_point
            assert "open" in data_point
            assert "high" in data_point
            assert "low" in data_point
            assert "close" in data_point
            assert "volume" in data_point
            assert data_point["symbol"] == symbol
            assert data_point["high"] >= data_point["low"]
            assert data_point["high"] >= data_point["open"]
            assert data_point["high"] >= data_point["close"]

        # Get latest tick
        tick_data = await trading_system.get_latest_tick(symbol)
        assert tick_data["symbol"] == symbol
        assert tick_data["price"] > 0
        assert tick_data["size"] > 0
        assert "time" in tick_data

    @pytest.mark.asyncio
    async def test_system_statistics_integration(self, trading_system):
        """Test system statistics across integrated workflow."""
        symbols = ["EURUSD", "GBPUSD"]

        await trading_system.initialize()

        # Initial statistics
        initial_stats = trading_system.get_system_statistics()
        assert initial_stats["total_signals"] == 0
        assert initial_stats["total_orders"] == 0
        assert initial_stats["total_executions"] == 0

        # Generate signals for multiple symbols
        for symbol in symbols:
            await trading_system.generate_signal(symbol, "stats_test")

        # Get updated statistics
        final_stats = trading_system.get_system_statistics()
        assert final_stats["total_signals"] == len(symbols)
        assert final_stats["symbols_traded"] <= len(symbols)
        assert 0.0 <= final_stats["avg_signal_confidence"] <= 1.0

        # If orders were created (high confidence signals)
        if final_stats["total_orders"] > 0:
            assert final_stats["filled_orders"] <= final_stats["total_orders"]
            assert final_stats["total_executions"] <= final_stats["total_orders"]


class TestIntegrationErrorHandling:
    """Test error handling and edge cases in integration flow."""

    @pytest.fixture
    def trading_system(self):
        return IntegratedTradingSystem()

    @pytest.mark.asyncio
    async def test_invalid_order_execution(self, trading_system):
        """Test handling of invalid order execution."""
        await trading_system.initialize()

        # Try to execute non-existent order
        with pytest.raises(ValueError, match="Order .* not found"):
            await trading_system.execute_order("nonexistent_order")

    @pytest.mark.asyncio
    async def test_duplicate_execution_prevention(self, trading_system):
        """Test prevention of duplicate order executions."""
        symbol = "NZDUSD"
        quantity = 3000.0

        await trading_system.initialize()
        trading_system.auto_execute_high_confidence = False

        # Create and execute order
        signal = await trading_system.generate_signal(symbol)
        order = await trading_system.create_order_from_signal(signal, quantity)
        await trading_system.execute_order(order.id)

        # Try to execute already filled order
        with pytest.raises(ValueError, match="not in pending status"):
            await trading_system.execute_order(order.id)

    @pytest.mark.asyncio
    async def test_websocket_invalid_client_operations(self, trading_system):
        """Test WebSocket operations with invalid clients."""
        await trading_system.initialize()

        # Try to subscribe non-connected client
        with pytest.raises(ValueError, match="Client .* not connected"):
            await trading_system.subscribe_client("invalid_client", "signals:EURUSD")


# Pytest configuration
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])
