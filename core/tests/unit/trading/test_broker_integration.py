"""
TDD Tests for Broker Integration and Smart Order Routing

Tests comprehensive broker adapter functionality including order routing,
execution, and failover for the FXML4 trading platform.
Following Red-Green-Refactor methodology.
"""

import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.trading.orders import Order, OrderSide, OrderState, OrderType
from core.trading.brokers import BrokerStatus


@pytest.mark.tdd
@pytest.mark.red
class TestBrokerAdapter:
    """
    RED Phase: Test broker adapter base class that doesn't exist yet.

    Tests cover broker connection, order submission, and status updates.
    """

    def test_broker_adapter_import(self):
        """RED: Test that we can import the BrokerAdapter base class."""
        from core.trading.brokers import BrokerAdapter, BrokerStatus

        adapter = BrokerAdapter(broker_id="TEST")
        assert adapter is not None
        assert adapter.broker_id == "TEST"

    def test_broker_status_enum(self):
        """RED: Test broker status enumeration."""
        from core.trading.brokers import BrokerStatus

        assert BrokerStatus.CONNECTED == "connected"
        assert BrokerStatus.DISCONNECTED == "disconnected"
        assert BrokerStatus.CONNECTING == "connecting"
        assert BrokerStatus.ERROR == "error"
        assert BrokerStatus.MAINTENANCE == "maintenance"

    @pytest.mark.asyncio
    async def test_broker_connect(self):
        """RED: Test broker connection."""
        from core.trading.brokers import BrokerAdapter, BrokerStatus

        adapter = BrokerAdapter(broker_id="IB")
        assert adapter.status == BrokerStatus.DISCONNECTED

        await adapter.connect()
        assert adapter.status == BrokerStatus.CONNECTED
        assert adapter.connected_at is not None

    @pytest.mark.asyncio
    async def test_broker_disconnect(self):
        """RED: Test broker disconnection."""
        from core.trading.brokers import BrokerAdapter, BrokerStatus

        adapter = BrokerAdapter(broker_id="IB")
        await adapter.connect()
        await adapter.disconnect()

        assert adapter.status == BrokerStatus.DISCONNECTED
        assert adapter.disconnected_at is not None

    @pytest.mark.asyncio
    async def test_submit_order(self):
        """RED: Test order submission to broker."""
        from core.trading.brokers import BrokerAdapter

        adapter = BrokerAdapter(broker_id="IB")
        await adapter.connect()

        order = Order(
            symbol="EUR/USD",
            side=OrderSide.BUY,
            quantity=100000,
            order_type=OrderType.MARKET,
            user_id="trader_123"
        )

        result = await adapter.submit_order(order)

        assert result["status"] == "accepted"
        assert "broker_order_id" in result
        assert result["broker_order_id"] is not None

    @pytest.mark.asyncio
    async def test_cancel_order(self):
        """RED: Test order cancellation."""
        from core.trading.brokers import BrokerAdapter

        adapter = BrokerAdapter(broker_id="IB")
        await adapter.connect()

        result = await adapter.cancel_order("IB123456")

        assert result["status"] == "cancelled"
        assert result["broker_order_id"] == "IB123456"

    @pytest.mark.asyncio
    async def test_get_order_status(self):
        """RED: Test getting order status."""
        from core.trading.brokers import BrokerAdapter

        adapter = BrokerAdapter(broker_id="IB")
        await adapter.connect()

        status = await adapter.get_order_status("IB123456")

        assert "state" in status
        assert "filled_quantity" in status
        assert "average_fill_price" in status

    @pytest.mark.asyncio
    async def test_connection_heartbeat(self):
        """RED: Test connection heartbeat monitoring."""
        from core.trading.brokers import BrokerAdapter, BrokerStatus

        adapter = BrokerAdapter(
            broker_id="IB",
            heartbeat_interval=1  # 1 second for testing
        )
        await adapter.connect()

        # Check initial heartbeat
        assert adapter.last_heartbeat is not None
        initial_heartbeat = adapter.last_heartbeat

        # Wait and check heartbeat updated
        await asyncio.sleep(1.1)
        assert adapter.last_heartbeat > initial_heartbeat
        assert adapter.status == BrokerStatus.CONNECTED

    @pytest.mark.asyncio
    async def test_connection_failure_handling(self):
        """RED: Test handling of connection failures."""
        from core.trading.brokers import BrokerAdapter, BrokerStatus

        adapter = BrokerAdapter(broker_id="IB")

        # Simulate connection failure
        with patch.object(adapter, '_connect', side_effect=Exception("Connection failed")):
            result = await adapter.connect()

        assert adapter.status == BrokerStatus.ERROR
        assert adapter.last_error is not None
        assert "Connection failed" in adapter.last_error


@pytest.mark.tdd
@pytest.mark.red
class TestIBAdapter:
    """
    RED Phase: Test Interactive Brokers adapter that doesn't exist yet.

    Tests cover IB-specific functionality.
    """

    def test_ib_adapter_import(self):
        """RED: Test that we can import the IB adapter."""
        from core.trading.brokers import IBAdapter

        adapter = IBAdapter(
            host="127.0.0.1",
            port=7497,
            client_id=1
        )
        assert adapter is not None
        assert adapter.broker_id == "IB"
        assert adapter.host == "127.0.0.1"
        assert adapter.port == 7497

    @pytest.mark.asyncio
    async def test_ib_contract_creation(self):
        """RED: Test IB contract creation from order."""
        from core.trading.brokers import IBAdapter

        adapter = IBAdapter()

        order = Order(
            symbol="EUR/USD",
            side=OrderSide.BUY,
            quantity=100000,
            order_type=OrderType.LIMIT,
            limit_price=Decimal("1.0900"),
            user_id="trader_123"
        )

        contract = adapter.create_contract(order)

        assert contract["symbol"] == "EUR"
        assert contract["currency"] == "USD"
        assert contract["sec_type"] == "CASH"
        assert contract["exchange"] == "IDEALPRO"

    @pytest.mark.asyncio
    async def test_ib_order_creation(self):
        """RED: Test IB order creation."""
        from core.trading.brokers import IBAdapter

        adapter = IBAdapter()

        order = Order(
            symbol="EUR/USD",
            side=OrderSide.BUY,
            quantity=100000,
            order_type=OrderType.LIMIT,
            limit_price=Decimal("1.0900"),
            user_id="trader_123"
        )

        ib_order = adapter.create_ib_order(order)

        assert ib_order["action"] == "BUY"
        assert ib_order["quantity"] == 100000
        assert ib_order["order_type"] == "LMT"
        assert ib_order["limit_price"] == 1.0900


@pytest.mark.tdd
@pytest.mark.red
class TestSmartOrderRouter:
    """
    RED Phase: Test smart order router that doesn't exist yet.

    Tests cover routing logic, broker selection, and failover.
    """

    def test_smart_router_import(self):
        """RED: Test that we can import the SmartOrderRouter."""
        from core.trading.brokers import SmartOrderRouter

        router = SmartOrderRouter()
        assert router is not None

    @pytest.mark.asyncio
    async def test_add_broker(self):
        """RED: Test adding brokers to the router."""
        from core.trading.brokers import SmartOrderRouter, BrokerAdapter

        router = SmartOrderRouter()

        broker1 = BrokerAdapter(broker_id="IB")
        broker2 = BrokerAdapter(broker_id="FXCM")

        await router.add_broker(broker1, priority=1)
        await router.add_broker(broker2, priority=2)

        assert len(router.brokers) == 2
        assert router.get_broker("IB") is not None
        assert router.get_broker("FXCM") is not None

    @pytest.mark.asyncio
    async def test_route_order_to_primary(self):
        """RED: Test routing order to primary broker."""
        from core.trading.brokers import SmartOrderRouter, BrokerAdapter

        router = SmartOrderRouter()

        # Mock brokers
        broker1 = MagicMock(spec=BrokerAdapter)
        broker1.broker_id = "IB"
        broker1.status = BrokerStatus.CONNECTED
        broker1.submit_order = AsyncMock(
            return_value={"status": "accepted", "broker_order_id": "IB123"}
        )

        await router.add_broker(broker1, priority=1)

        order = Order(
            symbol="EUR/USD",
            side=OrderSide.BUY,
            quantity=100000,
            order_type=OrderType.MARKET,
            user_id="trader_123"
        )

        result = await router.route_order(order)

        assert result["broker_id"] == "IB"
        assert result["broker_order_id"] == "IB123"
        broker1.submit_order.assert_called_once_with(order)

    @pytest.mark.asyncio
    async def test_failover_to_backup_broker(self):
        """RED: Test failover when primary broker is down."""
        from core.trading.brokers import SmartOrderRouter, BrokerAdapter, BrokerStatus

        router = SmartOrderRouter()

        # Primary broker (disconnected)
        broker1 = MagicMock(spec=BrokerAdapter)
        broker1.broker_id = "IB"
        broker1.status = BrokerStatus.DISCONNECTED

        # Backup broker (connected)
        broker2 = MagicMock(spec=BrokerAdapter)
        broker2.broker_id = "FXCM"
        broker2.status = BrokerStatus.CONNECTED
        broker2.submit_order = AsyncMock(
            return_value={"status": "accepted", "broker_order_id": "FXCM456"}
        )

        await router.add_broker(broker1, priority=1)
        await router.add_broker(broker2, priority=2)

        order = Order(
            symbol="EUR/USD",
            side=OrderSide.BUY,
            quantity=100000,
            order_type=OrderType.MARKET,
            user_id="trader_123"
        )

        result = await router.route_order(order)

        assert result["broker_id"] == "FXCM"
        assert result["broker_order_id"] == "FXCM456"
        broker2.submit_order.assert_called_once_with(order)

    @pytest.mark.asyncio
    async def test_route_by_symbol_preferences(self):
        """RED: Test routing based on symbol preferences."""
        from core.trading.brokers import SmartOrderRouter, BrokerAdapter

        router = SmartOrderRouter()

        # Configure symbol preferences
        router.set_symbol_preference("EUR/USD", "IB")
        router.set_symbol_preference("GBP/USD", "FXCM")

        # Mock brokers
        broker1 = MagicMock(spec=BrokerAdapter)
        broker1.broker_id = "IB"
        broker1.status = BrokerStatus.CONNECTED
        broker1.submit_order = AsyncMock(
            return_value={"status": "accepted", "broker_order_id": "IB123"}
        )

        broker2 = MagicMock(spec=BrokerAdapter)
        broker2.broker_id = "FXCM"
        broker2.status = BrokerStatus.CONNECTED
        broker2.submit_order = AsyncMock(
            return_value={"status": "accepted", "broker_order_id": "FXCM456"}
        )

        await router.add_broker(broker1, priority=2)  # Lower priority
        await router.add_broker(broker2, priority=1)  # Higher priority

        # Test EUR/USD routed to IB despite lower priority
        order1 = Order(
            symbol="EUR/USD",
            side=OrderSide.BUY,
            quantity=100000,
            order_type=OrderType.MARKET,
            user_id="trader_123"
        )

        result1 = await router.route_order(order1)
        assert result1["broker_id"] == "IB"

        # Test GBP/USD routed to FXCM
        order2 = Order(
            symbol="GBP/USD",
            side=OrderSide.SELL,
            quantity=50000,
            order_type=OrderType.MARKET,
            user_id="trader_123"
        )

        result2 = await router.route_order(order2)
        assert result2["broker_id"] == "FXCM"

    @pytest.mark.asyncio
    async def test_load_balancing(self):
        """RED: Test load balancing across multiple brokers."""
        from core.trading.brokers import SmartOrderRouter, BrokerAdapter

        router = SmartOrderRouter(load_balance=True)

        # Mock brokers with order counts
        broker1 = MagicMock(spec=BrokerAdapter)
        broker1.broker_id = "IB"
        broker1.status = BrokerStatus.CONNECTED
        broker1.submit_order = AsyncMock(
            return_value={"status": "accepted", "broker_order_id": "IB123"}
        )

        broker2 = MagicMock(spec=BrokerAdapter)
        broker2.broker_id = "FXCM"
        broker2.status = BrokerStatus.CONNECTED
        broker2.submit_order = AsyncMock(
            return_value={"status": "accepted", "broker_order_id": "FXCM456"}
        )

        await router.add_broker(broker1, priority=1)
        await router.add_broker(broker2, priority=1)  # Same priority

        # Submit multiple orders
        orders_routed = {"IB": 0, "FXCM": 0}

        for i in range(10):
            order = Order(
                symbol="EUR/USD",
                side=OrderSide.BUY,
                quantity=10000,
                order_type=OrderType.MARKET,
                user_id=f"trader_{i}"
            )

            result = await router.route_order(order)
            orders_routed[result["broker_id"]] += 1

        # Check load is balanced (roughly equal)
        assert orders_routed["IB"] > 0
        assert orders_routed["FXCM"] > 0
        assert abs(orders_routed["IB"] - orders_routed["FXCM"]) <= 2

    @pytest.mark.asyncio
    async def test_circuit_breaker(self):
        """RED: Test circuit breaker for failing brokers."""
        from core.trading.brokers import SmartOrderRouter, BrokerAdapter

        router = SmartOrderRouter(
            circuit_breaker_threshold=3,
            circuit_breaker_timeout=60
        )

        # Mock broker that fails
        broker = MagicMock(spec=BrokerAdapter)
        broker.broker_id = "IB"
        broker.status = BrokerStatus.CONNECTED
        broker.submit_order = AsyncMock(
            side_effect=Exception("Connection timeout")
        )

        await router.add_broker(broker, priority=1)

        # Try to submit orders until circuit breaks
        for i in range(3):
            order = Order(
                symbol="EUR/USD",
                side=OrderSide.BUY,
                quantity=10000,
                order_type=OrderType.MARKET,
                user_id="trader_123"
            )

            try:
                await router.route_order(order)
            except Exception:
                pass

        # Circuit should be open now
        assert router.is_circuit_open("IB") is True

        # New orders should be rejected immediately
        order = Order(
            symbol="EUR/USD",
            side=OrderSide.BUY,
            quantity=10000,
            order_type=OrderType.MARKET,
            user_id="trader_123"
        )

        with pytest.raises(Exception) as exc_info:
            await router.route_order(order)
        # Circuit is open, so no brokers are available
        assert "No available brokers" in str(exc_info.value)


@pytest.mark.tdd
@pytest.mark.red
class TestExecutionEngine:
    """
    RED Phase: Test execution engine that doesn't exist yet.

    Tests cover order execution, fill handling, and slippage management.
    """

    def test_execution_engine_import(self):
        """RED: Test that we can import the ExecutionEngine."""
        from core.trading.execution import ExecutionEngine

        engine = ExecutionEngine()
        assert engine is not None

    @pytest.mark.asyncio
    async def test_execute_market_order(self):
        """RED: Test executing a market order."""
        from core.trading.execution import ExecutionEngine
        from core.trading.brokers import SmartOrderRouter

        router = MagicMock(spec=SmartOrderRouter)
        router.route_order = AsyncMock(
            return_value={
                "status": "accepted",
                "broker_id": "IB",
                "broker_order_id": "IB123"
            }
        )

        engine = ExecutionEngine(router=router)

        order = Order(
            symbol="EUR/USD",
            side=OrderSide.BUY,
            quantity=100000,
            order_type=OrderType.MARKET,
            user_id="trader_123"
        )

        result = await engine.execute_order(order)

        assert result["status"] == "executed"
        assert result["broker_id"] == "IB"
        assert result["broker_order_id"] == "IB123"

    @pytest.mark.asyncio
    async def test_slippage_calculation(self):
        """RED: Test slippage calculation for executed orders."""
        from core.trading.execution import ExecutionEngine

        engine = ExecutionEngine()

        # Expected price vs actual fill price
        expected_price = Decimal("1.0950")
        fill_price = Decimal("1.0952")
        quantity = 100000

        slippage = engine.calculate_slippage(
            expected_price=expected_price,
            fill_price=fill_price,
            quantity=quantity,
            side=OrderSide.BUY
        )

        # For buy orders, positive slippage is bad (paid more)
        assert slippage["pips"] == Decimal("2")  # 0.0002 * 10000
        assert slippage["cost"] == Decimal("20")  # 0.0002 * 100000

    @pytest.mark.asyncio
    async def test_spread_monitoring(self):
        """RED: Test bid-ask spread monitoring."""
        from core.trading.execution import ExecutionEngine

        engine = ExecutionEngine()

        # Mock price feed
        price_feed = MagicMock()
        price_feed.get_quote = AsyncMock(
            return_value={
                "bid": Decimal("1.0948"),
                "ask": Decimal("1.0950"),
                "timestamp": datetime.now()
            }
        )
        engine.price_feed = price_feed

        spread = await engine.get_spread("EUR/USD")

        assert spread["bid"] == Decimal("1.0948")
        assert spread["ask"] == Decimal("1.0950")
        assert spread["spread_pips"] == Decimal("2")
        assert spread["spread_percentage"] == Decimal("0.0183")  # Approximate

    @pytest.mark.asyncio
    async def test_execution_with_max_slippage(self):
        """RED: Test order rejection when slippage exceeds limit."""
        from core.trading.execution import ExecutionEngine
        from core.trading.brokers import SmartOrderRouter

        # Mock router
        router = MagicMock(spec=SmartOrderRouter)
        router.route_order = AsyncMock(
            return_value={
                "status": "accepted",
                "broker_id": "IB",
                "broker_order_id": "IB123"
            }
        )

        engine = ExecutionEngine(router=router, max_slippage_pips=5)

        order = Order(
            symbol="EUR/USD",
            side=OrderSide.BUY,
            quantity=100000,
            order_type=OrderType.MARKET,
            user_id="trader_123"
        )

        # Mock execution with high slippage
        with patch.object(
            engine,
            '_get_expected_price',
            return_value=Decimal("1.0950")
        ):
            with patch.object(
                engine,
                '_get_fill_price',
                return_value=Decimal("1.0960")  # 10 pips slippage
            ):
                with pytest.raises(Exception) as exc_info:
                    await engine.execute_order(order)

                assert "Slippage exceeds maximum" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_partial_fill_handling(self):
        """RED: Test handling of partial fills."""
        from core.trading.execution import ExecutionEngine

        engine = ExecutionEngine()

        order = Order(
            symbol="EUR/USD",
            side=OrderSide.BUY,
            quantity=100000,
            order_type=OrderType.LIMIT,
            limit_price=Decimal("1.0950"),
            user_id="trader_123"
        )

        # Must validate and submit order before fills
        order.state = OrderState.SUBMITTED

        # Simulate multiple partial fills
        fills = [
            {"quantity": 30000, "price": Decimal("1.0950"), "timestamp": datetime.now()},
            {"quantity": 40000, "price": Decimal("1.0951"), "timestamp": datetime.now()},
            {"quantity": 30000, "price": Decimal("1.0950"), "timestamp": datetime.now()},
        ]

        for fill in fills:
            await engine.handle_fill(order, fill)

        assert order.state == OrderState.FILLED
        assert order.filled_quantity == 100000
        # Weighted average: (30000*1.0950 + 40000*1.0951 + 30000*1.0950) / 100000
        expected_avg = Decimal("1.09504")
        assert abs(order.average_fill_price - expected_avg) < Decimal("0.00001")