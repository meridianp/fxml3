"""
TDD Tests for Position Tracking and P&L Calculation

Tests comprehensive position management functionality including tracking,
P&L calculation, and position aggregation for the FXML4 trading platform.
Following Red-Green-Refactor methodology.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.trading.orders import Order, OrderSide, OrderState, OrderType


@pytest.mark.tdd
@pytest.mark.red
class TestPositionModel:
    """
    RED Phase: Test position tracking model that doesn't exist yet.

    Tests cover position creation, updates, and P&L calculations.
    """

    def test_position_import(self):
        """RED: Test that we can import the Position model."""
        from core.trading.positions import Position, PositionSide

        position = Position(
            symbol="EUR/USD",
            quantity=100000,
            entry_price=Decimal("1.0950"),
            side=PositionSide.LONG,
            user_id="trader_123"
        )
        assert position is not None
        assert position.symbol == "EUR/USD"

    def test_position_side_enum(self):
        """RED: Test position side enumeration."""
        from core.trading.positions import PositionSide

        assert PositionSide.LONG == "long"
        assert PositionSide.SHORT == "short"
        assert PositionSide.FLAT == "flat"

    def test_create_long_position(self):
        """RED: Test creating a long position."""
        from core.trading.positions import Position, PositionSide

        position = Position(
            symbol="EUR/USD",
            quantity=100000,
            entry_price=Decimal("1.0950"),
            side=PositionSide.LONG,
            user_id="trader_123"
        )

        assert position.position_id is not None
        assert len(position.position_id) == 36  # UUID format
        assert position.symbol == "EUR/USD"
        assert position.quantity == 100000
        assert position.entry_price == Decimal("1.0950")
        assert position.side == PositionSide.LONG
        assert position.user_id == "trader_123"
        assert position.created_at is not None
        assert position.updated_at is not None
        assert position.is_open is True
        assert position.realized_pnl == Decimal("0")
        assert position.commission_paid == Decimal("0")

    def test_create_short_position(self):
        """RED: Test creating a short position."""
        from core.trading.positions import Position, PositionSide

        position = Position(
            symbol="GBP/USD",
            quantity=50000,
            entry_price=Decimal("1.2750"),
            side=PositionSide.SHORT,
            user_id="trader_456"
        )

        assert position.side == PositionSide.SHORT
        assert position.quantity == 50000
        assert position.entry_price == Decimal("1.2750")

    def test_calculate_unrealized_pnl_long(self):
        """RED: Test unrealized P&L calculation for long position."""
        from core.trading.positions import Position, PositionSide

        position = Position(
            symbol="EUR/USD",
            quantity=100000,
            entry_price=Decimal("1.0950"),
            side=PositionSide.LONG,
            user_id="trader_123"
        )

        # Price increased - profit
        unrealized_pnl = position.calculate_unrealized_pnl(
            current_price=Decimal("1.1000")
        )
        # (1.1000 - 1.0950) * 100000 = 500
        assert unrealized_pnl == Decimal("500")

        # Price decreased - loss
        unrealized_pnl = position.calculate_unrealized_pnl(
            current_price=Decimal("1.0900")
        )
        # (1.0900 - 1.0950) * 100000 = -500
        assert unrealized_pnl == Decimal("-500")

    def test_calculate_unrealized_pnl_short(self):
        """RED: Test unrealized P&L calculation for short position."""
        from core.trading.positions import Position, PositionSide

        position = Position(
            symbol="EUR/USD",
            quantity=100000,
            entry_price=Decimal("1.0950"),
            side=PositionSide.SHORT,
            user_id="trader_123"
        )

        # Price decreased - profit for short
        unrealized_pnl = position.calculate_unrealized_pnl(
            current_price=Decimal("1.0900")
        )
        # (1.0950 - 1.0900) * 100000 = 500
        assert unrealized_pnl == Decimal("500")

        # Price increased - loss for short
        unrealized_pnl = position.calculate_unrealized_pnl(
            current_price=Decimal("1.1000")
        )
        # (1.0950 - 1.1000) * 100000 = -500
        assert unrealized_pnl == Decimal("-500")

    def test_close_position_with_profit(self):
        """RED: Test closing a position with profit."""
        from core.trading.positions import Position, PositionSide

        position = Position(
            symbol="EUR/USD",
            quantity=100000,
            entry_price=Decimal("1.0950"),
            side=PositionSide.LONG,
            user_id="trader_123"
        )

        position.close(
            exit_price=Decimal("1.1000"),
            commission=Decimal("5.00")
        )

        assert position.is_open is False
        assert position.exit_price == Decimal("1.1000")
        assert position.closed_at is not None
        # (1.1000 - 1.0950) * 100000 - 5.00 = 495
        assert position.realized_pnl == Decimal("495")
        assert position.commission_paid == Decimal("5.00")

    def test_close_position_with_loss(self):
        """RED: Test closing a position with loss."""
        from core.trading.positions import Position, PositionSide

        position = Position(
            symbol="EUR/USD",
            quantity=100000,
            entry_price=Decimal("1.0950"),
            side=PositionSide.LONG,
            user_id="trader_123"
        )

        position.close(
            exit_price=Decimal("1.0900"),
            commission=Decimal("5.00")
        )

        assert position.is_open is False
        # (1.0900 - 1.0950) * 100000 - 5.00 = -505
        assert position.realized_pnl == Decimal("-505")

    def test_partial_close(self):
        """RED: Test partial position closing."""
        from core.trading.positions import Position, PositionSide

        position = Position(
            symbol="EUR/USD",
            quantity=100000,
            entry_price=Decimal("1.0950"),
            side=PositionSide.LONG,
            user_id="trader_123"
        )

        # Close 30% of position
        closed_position = position.partial_close(
            close_quantity=30000,
            exit_price=Decimal("1.1000"),
            commission=Decimal("1.50")
        )

        # Original position reduced
        assert position.quantity == 70000
        assert position.is_open is True

        # New closed position created
        assert closed_position.quantity == 30000
        assert closed_position.is_open is False
        assert closed_position.exit_price == Decimal("1.1000")
        # (1.1000 - 1.0950) * 30000 - 1.50 = 148.50
        assert closed_position.realized_pnl == Decimal("148.50")

    def test_position_to_dict(self):
        """RED: Test position serialization to dictionary."""
        from core.trading.positions import Position, PositionSide

        position = Position(
            symbol="EUR/USD",
            quantity=100000,
            entry_price=Decimal("1.0950"),
            side=PositionSide.LONG,
            user_id="trader_123",
            notes="Test position"
        )

        position_dict = position.to_dict()

        assert position_dict["position_id"] == position.position_id
        assert position_dict["symbol"] == "EUR/USD"
        assert position_dict["quantity"] == 100000
        assert position_dict["entry_price"] == "1.0950"
        assert position_dict["side"] == "long"
        assert position_dict["user_id"] == "trader_123"
        assert position_dict["is_open"] is True
        assert position_dict["realized_pnl"] == "0"
        assert position_dict["notes"] == "Test position"

    def test_position_from_dict(self):
        """RED: Test position deserialization from dictionary."""
        from core.trading.positions import Position

        position_data = {
            "position_id": "550e8400-e29b-41d4-a716-446655440000",
            "symbol": "GBP/USD",
            "quantity": 50000,
            "entry_price": "1.2750",
            "side": "short",
            "user_id": "trader_456",
            "is_open": True,
            "realized_pnl": "0",
            "commission_paid": "0",
            "created_at": "2024-01-15T10:30:00Z",
            "updated_at": "2024-01-15T10:30:00Z"
        }

        position = Position.from_dict(position_data)

        assert position.position_id == "550e8400-e29b-41d4-a716-446655440000"
        assert position.symbol == "GBP/USD"
        assert position.quantity == 50000
        assert position.entry_price == Decimal("1.2750")
        assert position.side.value == "short"


@pytest.mark.tdd
@pytest.mark.red
class TestPositionManager:
    """
    RED Phase: Test position manager that doesn't exist yet.

    Tests cover position lifecycle management and aggregation.
    """

    def test_position_manager_import(self):
        """RED: Test that we can import the PositionManager."""
        from core.trading.positions import PositionManager

        manager = PositionManager()
        assert manager is not None

    @pytest.mark.asyncio
    async def test_open_position_from_order(self):
        """RED: Test opening a position from a filled order."""
        from core.trading.positions import PositionManager
        from core.trading.orders import Order, OrderSide, OrderType

        manager = PositionManager()

        # Create a filled buy order
        order = Order(
            symbol="EUR/USD",
            side=OrderSide.BUY,
            quantity=100000,
            order_type=OrderType.MARKET,
            user_id="trader_123"
        )
        order.state = OrderState.FILLED
        order.filled_quantity = 100000
        order.average_fill_price = Decimal("1.0950")
        order.commission = Decimal("2.50")

        position = await manager.open_position_from_order(order)

        assert position.symbol == "EUR/USD"
        assert position.quantity == 100000
        assert position.entry_price == Decimal("1.0950")
        assert position.side.value == "long"  # Buy order creates long position
        assert position.commission_paid == Decimal("2.50")

    @pytest.mark.asyncio
    async def test_update_position_from_order(self):
        """RED: Test updating existing position from a new order."""
        from core.trading.positions import PositionManager, Position, PositionSide
        from core.trading.orders import Order, OrderSide, OrderType

        manager = PositionManager()

        # Create initial position
        position = Position(
            symbol="EUR/USD",
            quantity=100000,
            entry_price=Decimal("1.0950"),
            side=PositionSide.LONG,
            user_id="trader_123"
        )
        manager.positions[position.position_id] = position

        # Create another buy order (adding to position)
        order = Order(
            symbol="EUR/USD",
            side=OrderSide.BUY,
            quantity=50000,
            order_type=OrderType.MARKET,
            user_id="trader_123"
        )
        order.state = OrderState.FILLED
        order.filled_quantity = 50000
        order.average_fill_price = Decimal("1.0960")
        order.commission = Decimal("1.25")

        updated_position = await manager.update_position_from_order(
            position.position_id, order
        )

        assert updated_position.quantity == 150000  # 100000 + 50000
        # Weighted average: (100000 * 1.0950 + 50000 * 1.0960) / 150000
        expected_avg = (Decimal("100000") * Decimal("1.0950") +
                        Decimal("50000") * Decimal("1.0960")) / Decimal("150000")
        assert abs(updated_position.entry_price - expected_avg) < Decimal("0.0001")
        assert updated_position.commission_paid == Decimal("1.25")

    @pytest.mark.asyncio
    async def test_close_position_from_order(self):
        """RED: Test closing a position from an opposite order."""
        from core.trading.positions import PositionManager, Position, PositionSide
        from core.trading.orders import Order, OrderSide, OrderType

        manager = PositionManager()

        # Create long position
        position = Position(
            symbol="EUR/USD",
            quantity=100000,
            entry_price=Decimal("1.0950"),
            side=PositionSide.LONG,
            user_id="trader_123"
        )
        manager.positions[position.position_id] = position

        # Create sell order to close position
        order = Order(
            symbol="EUR/USD",
            side=OrderSide.SELL,
            quantity=100000,
            order_type=OrderType.MARKET,
            user_id="trader_123"
        )
        order.state = OrderState.FILLED
        order.filled_quantity = 100000
        order.average_fill_price = Decimal("1.1000")
        order.commission = Decimal("2.50")

        closed_position = await manager.close_position_from_order(
            position.position_id, order
        )

        assert closed_position.is_open is False
        assert closed_position.exit_price == Decimal("1.1000")
        # (1.1000 - 1.0950) * 100000 - 2.50 = 497.50
        assert closed_position.realized_pnl == Decimal("497.50")

    @pytest.mark.asyncio
    async def test_get_open_positions(self):
        """RED: Test retrieving open positions."""
        from core.trading.positions import PositionManager, Position, PositionSide

        manager = PositionManager()

        # Create positions
        pos1 = Position(
            symbol="EUR/USD",
            quantity=100000,
            entry_price=Decimal("1.0950"),
            side=PositionSide.LONG,
            user_id="trader_123"
        )
        manager.positions[pos1.position_id] = pos1

        pos2 = Position(
            symbol="GBP/USD",
            quantity=50000,
            entry_price=Decimal("1.2750"),
            side=PositionSide.SHORT,
            user_id="trader_123"
        )
        manager.positions[pos2.position_id] = pos2

        # Close one position
        pos2.close(exit_price=Decimal("1.2700"), commission=Decimal("1.25"))

        open_positions = await manager.get_open_positions()

        assert len(open_positions) == 1
        assert open_positions[0].position_id == pos1.position_id

    @pytest.mark.asyncio
    async def test_get_user_positions(self):
        """RED: Test retrieving positions by user."""
        from core.trading.positions import PositionManager, Position, PositionSide

        manager = PositionManager()

        # Create positions for different users
        pos1 = Position(
            symbol="EUR/USD",
            quantity=100000,
            entry_price=Decimal("1.0950"),
            side=PositionSide.LONG,
            user_id="trader_123"
        )
        manager.positions[pos1.position_id] = pos1

        pos2 = Position(
            symbol="GBP/USD",
            quantity=50000,
            entry_price=Decimal("1.2750"),
            side=PositionSide.SHORT,
            user_id="trader_123"
        )
        manager.positions[pos2.position_id] = pos2

        pos3 = Position(
            symbol="USD/JPY",
            quantity=100000,
            entry_price=Decimal("150.00"),
            side=PositionSide.LONG,
            user_id="trader_456"
        )
        manager.positions[pos3.position_id] = pos3

        user_positions = await manager.get_user_positions("trader_123")

        assert len(user_positions) == 2
        position_ids = [p.position_id for p in user_positions]
        assert pos1.position_id in position_ids
        assert pos2.position_id in position_ids
        assert pos3.position_id not in position_ids

    @pytest.mark.asyncio
    async def test_calculate_total_pnl(self):
        """RED: Test calculating total P&L for a user."""
        from core.trading.positions import PositionManager, Position, PositionSide

        manager = PositionManager()

        # Mock price provider
        price_provider = MagicMock()
        price_provider.get_price = AsyncMock(side_effect=lambda symbol: {
            "EUR/USD": Decimal("1.1000"),
            "GBP/USD": Decimal("1.2700")
        }.get(symbol))

        manager.price_provider = price_provider

        # Create positions
        pos1 = Position(
            symbol="EUR/USD",
            quantity=100000,
            entry_price=Decimal("1.0950"),
            side=PositionSide.LONG,
            user_id="trader_123"
        )
        manager.positions[pos1.position_id] = pos1

        pos2 = Position(
            symbol="GBP/USD",
            quantity=50000,
            entry_price=Decimal("1.2750"),
            side=PositionSide.SHORT,
            user_id="trader_123"
        )
        manager.positions[pos2.position_id] = pos2

        # Close one position with realized P&L
        pos2.close(exit_price=Decimal("1.2700"), commission=Decimal("1.25"))

        total_pnl = await manager.calculate_total_pnl("trader_123")

        # Unrealized: (1.1000 - 1.0950) * 100000 = 500
        # Realized: (1.2750 - 1.2700) * 50000 - 1.25 = 248.75
        # Total: 500 + 248.75 = 748.75
        assert total_pnl["unrealized_pnl"] == Decimal("500")
        assert total_pnl["realized_pnl"] == Decimal("248.75")
        assert total_pnl["total_pnl"] == Decimal("748.75")

    @pytest.mark.asyncio
    async def test_get_position_by_symbol(self):
        """RED: Test getting position by symbol."""
        from core.trading.positions import PositionManager, Position, PositionSide

        manager = PositionManager()

        pos1 = Position(
            symbol="EUR/USD",
            quantity=100000,
            entry_price=Decimal("1.0950"),
            side=PositionSide.LONG,
            user_id="trader_123"
        )
        manager.positions[pos1.position_id] = pos1

        pos2 = Position(
            symbol="GBP/USD",
            quantity=50000,
            entry_price=Decimal("1.2750"),
            side=PositionSide.SHORT,
            user_id="trader_123"
        )
        manager.positions[pos2.position_id] = pos2

        eur_position = await manager.get_position_by_symbol("trader_123", "EUR/USD")

        assert eur_position is not None
        assert eur_position.symbol == "EUR/USD"
        assert eur_position.position_id == pos1.position_id

    @pytest.mark.asyncio
    async def test_aggregate_positions_by_symbol(self):
        """RED: Test aggregating multiple positions for the same symbol."""
        from core.trading.positions import PositionManager, Position, PositionSide

        manager = PositionManager()

        # Multiple long positions in EUR/USD
        pos1 = Position(
            symbol="EUR/USD",
            quantity=50000,
            entry_price=Decimal("1.0950"),
            side=PositionSide.LONG,
            user_id="trader_123"
        )
        manager.positions[pos1.position_id] = pos1

        pos2 = Position(
            symbol="EUR/USD",
            quantity=30000,
            entry_price=Decimal("1.0960"),
            side=PositionSide.LONG,
            user_id="trader_123"
        )
        manager.positions[pos2.position_id] = pos2

        # Short position (reduces net exposure)
        pos3 = Position(
            symbol="EUR/USD",
            quantity=20000,
            entry_price=Decimal("1.0970"),
            side=PositionSide.SHORT,
            user_id="trader_123"
        )
        manager.positions[pos3.position_id] = pos3

        aggregated = await manager.aggregate_positions("trader_123", "EUR/USD")

        # Net position: 50000 + 30000 - 20000 = 60000 long
        assert aggregated["net_quantity"] == 60000
        assert aggregated["net_side"] == "long"
        assert aggregated["long_quantity"] == 80000
        assert aggregated["short_quantity"] == 20000
        # Weighted average for longs: (50000 * 1.0950 + 30000 * 1.0960) / 80000
        expected_long_avg = (Decimal("50000") * Decimal("1.0950") +
                             Decimal("30000") * Decimal("1.0960")) / Decimal("80000")
        assert abs(aggregated["average_long_price"] - expected_long_avg) < Decimal("0.0001")
        assert aggregated["average_short_price"] == Decimal("1.0970")