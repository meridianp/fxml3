"""Tests for Position Manager."""

import pytest
import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import Mock, patch, AsyncMock

from fxml4_trade_manager.position_manager import (
    PositionManager, Position, PositionState
)
from fxml4_trade_manager.domain import (
    OrderSide, MockTimeProvider, MockEventPublisher,
    InMemoryMetricsCollector, UTCTimeProvider
)
from .fixtures import *  # Import all fixtures


@pytest.fixture
def position_manager(mock_time_provider, mock_event_publisher, mock_metrics_collector):
    """Create position manager instance with dependencies."""
    return PositionManager(
        time_provider=mock_time_provider,
        event_publisher=mock_event_publisher,
        metrics_collector=mock_metrics_collector
    )


class TestPosition:
    """Test Position class."""
    
    def test_position_initialization(self, sample_position_data, mock_time_provider):
        """Test position initialization."""
        position = Position(sample_position_data, mock_time_provider)
        
        assert position.position_id == 'pos_123'
        assert position.signal_id == 'sig_456'
        assert position.symbol == 'EURUSD'
        assert position.side == OrderSide.BUY
        assert position.state == PositionState.PENDING
        assert position.target_quantity == Decimal('10000')
        assert position.stop_loss == Decimal('1.0950')
    
    def test_position_to_dict(self, sample_position_data, mock_time_provider):
        """Test position to dictionary conversion."""
        position = Position(sample_position_data, mock_time_provider)
        pos_dict = position.to_dict()
        
        assert pos_dict['position_id'] == 'pos_123'
        assert pos_dict['symbol'] == 'EURUSD'
        assert pos_dict['side'] == 'BUY'
        assert pos_dict['state'] == 'pending'
        assert pos_dict['target_quantity'] == '10000'
    
    def test_update_price_buy_position(self, sample_position_data, mock_time_provider):
        """Test price update for buy position."""
        position = Position(sample_position_data, mock_time_provider)
        position.filled_quantity = Decimal('10000')
        position.avg_entry_price = Decimal('1.1000')
        
        # Price increases
        position.update_price(Decimal('1.1050'))
        
        assert position.current_price == Decimal('1.1050')
        assert position.highest_price == Decimal('1.1050')
        assert position.unrealized_pnl == Decimal('50')  # (1.1050 - 1.1000) * 10000 = 0.0050 * 10000 = 50
    
    def test_update_price_sell_position(self, sample_position_data, mock_time_provider):
        """Test price update for sell position."""
        sample_position_data['side'] = 'SELL'
        position = Position(sample_position_data, mock_time_provider)
        position.filled_quantity = Decimal('10000')
        position.avg_entry_price = Decimal('1.1000')
        
        # Price decreases
        position.update_price(Decimal('1.0950'))
        
        assert position.current_price == Decimal('1.0950')
        assert position.lowest_price == Decimal('1.0950')
        assert position.unrealized_pnl == Decimal('50')  # (1.1000 - 1.0950) * 10000
    
    def test_add_fill(self, sample_position_data, mock_time_provider):
        """Test adding fills to position."""
        position = Position(sample_position_data, mock_time_provider)
        # Start in OPENING state to test state transition
        position.state = PositionState.OPENING
        
        # First fill
        position.add_fill(Decimal('5000'), Decimal('1.1000'), Decimal('5'))
        
        assert position.filled_quantity == Decimal('5000')
        assert position.avg_entry_price == Decimal('1.1000')
        assert position.commission == Decimal('5')
        
        # Second fill at different price
        position.add_fill(Decimal('5000'), Decimal('1.1010'), Decimal('5'))
        
        assert position.filled_quantity == Decimal('10000')
        assert position.avg_entry_price == Decimal('1.1005')  # Weighted average
        assert position.commission == Decimal('10')
        assert position.state == PositionState.OPEN
    
    def test_add_exit(self, sample_position_data, mock_time_provider):
        """Test adding exits to position."""
        position = Position(sample_position_data, mock_time_provider)
        position.filled_quantity = Decimal('10000')
        position.remaining_quantity = Decimal('10000')
        position.avg_entry_price = Decimal('1.1000')
        position.state = PositionState.OPEN
        
        # Partial exit with profit
        position.add_exit(Decimal('5000'), Decimal('1.1050'), Decimal('5'))
        
        assert position.remaining_quantity == Decimal('5000')
        assert position.realized_pnl == Decimal('25')  # (1.1050 - 1.1000) * 5000 = 0.0050 * 5000 = 25
        assert position.commission == Decimal('5')
        assert position.state == PositionState.SCALING_OUT
        
        # Complete exit
        position.add_exit(Decimal('5000'), Decimal('1.1100'), Decimal('5'))
        
        assert position.remaining_quantity == Decimal('0')
        assert position.realized_pnl == Decimal('75')  # 25 + (1.1100 - 1.1000) * 5000 = 25 + 50 = 75
        assert position.commission == Decimal('10')
        assert position.state == PositionState.CLOSED
        assert position.closed_at is not None


class TestPositionManager:
    """Test PositionManager class."""
    
    @pytest.mark.asyncio
    async def test_create_position(self, position_manager, sample_position_data):
        """Test creating a position."""
        position_dict = await position_manager.create_position(sample_position_data)
        
        assert position_dict['position_id'] == 'pos_123'
        assert position_dict['symbol'] == 'EURUSD'
        assert 'pos_123' in position_manager.positions
        assert 'sig_456' in position_manager.positions_by_signal
        assert 'EURUSD' in position_manager.positions_by_symbol
    
    @pytest.mark.asyncio
    async def test_get_position(self, position_manager, sample_position_data):
        """Test getting position by ID."""
        await position_manager.create_position(sample_position_data)
        
        position_dict = await position_manager.get_position('pos_123')
        assert position_dict is not None
        assert position_dict['position_id'] == 'pos_123'
        
        # Non-existent position
        position = await position_manager.get_position('invalid_id')
        assert position is None
    
    @pytest.mark.asyncio
    async def test_get_positions_by_signal(self, position_manager, sample_position_data):
        """Test getting positions by signal ID."""
        # Create multiple positions for same signal
        await position_manager.create_position(sample_position_data)
        
        sample_position_data['position_id'] = 'pos_124'
        await position_manager.create_position(sample_position_data)
        
        positions = await position_manager.get_positions_by_signal('sig_456')
        assert len(positions) == 2
        assert all(p.signal_id == 'sig_456' for p in positions)
    
    @pytest.mark.asyncio
    async def test_get_positions_by_symbol(self, position_manager, sample_position_data):
        """Test getting positions by symbol."""
        # Create positions for same symbol
        await position_manager.create_position(sample_position_data)
        
        sample_position_data['position_id'] = 'pos_124'
        await position_manager.create_position(sample_position_data)
        
        positions = await position_manager.get_positions_by_symbol('EURUSD')
        assert len(positions) == 2
        assert all(p.symbol == 'EURUSD' for p in positions)
    
    @pytest.mark.asyncio
    async def test_get_open_positions(self, position_manager, sample_position_data):
        """Test getting open positions."""
        # Create positions in different states
        pos1_data = sample_position_data.copy()
        pos1_data['position_id'] = 'pos_1'
        pos1_data['state'] = 'open'
        pos1 = await position_manager.create_position(pos1_data)
        
        pos2_data = sample_position_data.copy()
        pos2_data['position_id'] = 'pos_2'
        pos2_data['state'] = 'scaling_out'
        pos2 = await position_manager.create_position(pos2_data)
        
        pos3_data = sample_position_data.copy()
        pos3_data['position_id'] = 'pos_3'
        pos3_data['state'] = 'closed'
        pos3 = await position_manager.create_position(pos3_data)
        
        open_positions = await position_manager.get_open_positions()
        assert len(open_positions) == 2
        assert all(p['state'] in ['open', 'scaling_out'] for p in open_positions)
    
    @pytest.mark.asyncio
    async def test_update_position_state(self, position_manager, sample_position_data):
        """Test updating position state."""
        position_dict = await position_manager.create_position(sample_position_data)
        
        # Update to OPEN
        success = await position_manager.update_position_state('pos_123', PositionState.OPEN)
        assert success
        position = position_manager.positions['pos_123']
        assert position.state == PositionState.OPEN
        assert position.opened_at is not None
        
        # Update to CLOSED
        success = await position_manager.update_position_state('pos_123', PositionState.CLOSED)
        assert success
        assert position.state == PositionState.CLOSED
        assert position.closed_at is not None
        assert 'pos_123' in position_manager.closed_positions
        assert 'pos_123' not in position_manager.positions
    
    @pytest.mark.asyncio
    async def test_update_position_fill(self, position_manager, sample_position_data):
        """Test updating position with fills."""
        position_dict = await position_manager.create_position(sample_position_data)
        
        success = await position_manager.update_position_fill(
            'pos_123', Decimal('5000'), Decimal('1.1000'), Decimal('5')
        )
        
        assert success
        position = position_manager.positions['pos_123']
        assert position.filled_quantity == Decimal('5000')
        assert position.commission == Decimal('5')
    
    @pytest.mark.asyncio
    async def test_update_position_exit(self, position_manager, sample_position_data):
        """Test updating position with exits."""
        position_dict = await position_manager.create_position(sample_position_data)
        position = position_manager.positions['pos_123']
        position.filled_quantity = Decimal('10000')
        position.remaining_quantity = Decimal('10000')
        position.avg_entry_price = Decimal('1.1000')
        position.state = PositionState.OPEN
        
        success = await position_manager.update_position_exit(
            'pos_123', Decimal('5000'), Decimal('1.1050'), Decimal('5')
        )
        
        assert success
        assert position.remaining_quantity == Decimal('5000')
        assert position.realized_pnl == Decimal('25')  # Fixed from 250
    
    @pytest.mark.asyncio
    async def test_update_position_price(self, position_manager, sample_position_data):
        """Test updating position price."""
        position_dict = await position_manager.create_position(sample_position_data)
        
        success = await position_manager.update_position_price('pos_123', Decimal('1.1050'))
        
        assert success
        position = position_manager.positions['pos_123']
        assert position.current_price == Decimal('1.1050')
        assert position.highest_price == Decimal('1.1050')
    
    @pytest.mark.asyncio
    async def test_update_stop_loss(self, position_manager, sample_position_data):
        """Test updating stop loss."""
        position_dict = await position_manager.create_position(sample_position_data)
        
        success = await position_manager.update_stop_loss('pos_123', Decimal('1.0975'))
        
        assert success
        position = position_manager.positions['pos_123']
        assert position.stop_loss == Decimal('1.0975')
    
    @pytest.mark.asyncio
    async def test_activate_trailing_stop(self, position_manager, sample_position_data):
        """Test activating trailing stop."""
        position_dict = await position_manager.create_position(sample_position_data)
        position = position_manager.positions['pos_123']
        position.current_price = Decimal('1.1050')
        
        success = await position_manager.activate_trailing_stop('pos_123', Decimal('0.0050'))
        
        assert success
        assert position.trailing_stop_active is True
        assert position.trailing_stop_distance == Decimal('0.0050')
        assert position.highest_price == Decimal('1.1050')
    
    @pytest.mark.asyncio
    async def test_calculate_trailing_stop(self, position_manager, sample_position_data):
        """Test calculating trailing stop level."""
        position_dict = await position_manager.create_position(sample_position_data)
        position = position_manager.positions['pos_123']
        position.side = OrderSide.BUY
        position.trailing_stop_active = True
        position.trailing_stop_distance = Decimal('0.0050')
        position.highest_price = Decimal('1.1100')
        
        trailing_stop = await position_manager.calculate_trailing_stop('pos_123')
        
        assert trailing_stop == Decimal('1.1050')  # 1.1100 - 0.0050
    
    @pytest.mark.asyncio
    async def test_get_position_metrics(self, position_manager, sample_position_data):
        """Test getting position metrics."""
        position_dict = await position_manager.create_position(sample_position_data)
        position = position_manager.positions['pos_123']
        position.filled_quantity = Decimal('10000')
        position.avg_entry_price = Decimal('1.1000')
        position.current_price = Decimal('1.1050')
        position.realized_pnl = Decimal('250')
        position.unrealized_pnl = Decimal('500')
        position.commission = Decimal('10')
        position.opened_at = position._time_provider.now() - timedelta(minutes=30)
        
        metrics = await position_manager.get_position_metrics('pos_123')
        
        assert metrics['position_id'] == 'pos_123'
        assert metrics['symbol'] == 'EURUSD'
        assert metrics['filled_quantity'] == 10000
        assert metrics['total_pnl'] == 750  # 250 + 500
        assert metrics['pnl_percent'] > 0
        assert metrics['duration_minutes'] >= 30
        assert metrics['risk_reward_ratio'] > 0
    
    @pytest.mark.asyncio
    async def test_cleanup_stale_positions(self, position_manager, sample_position_data):
        """Test cleaning up old closed positions."""
        # Create closed position
        position_dict = await position_manager.create_position(sample_position_data)
        position = position_manager.positions['pos_123']
        position.state = PositionState.CLOSED
        position.closed_at = position._time_provider.now() - timedelta(hours=25)
        
        # Move to closed positions
        position_manager.closed_positions['pos_123'] = position
        del position_manager.positions['pos_123']
        
        # Clean up positions older than 24 hours
        await position_manager.cleanup_stale_positions(max_age_hours=24)
        
        assert 'pos_123' not in position_manager.closed_positions
    
    @pytest.mark.asyncio
    async def test_position_index_cleanup(self, position_manager, sample_position_data):
        """Test that indexes are properly cleaned up when positions are closed."""
        position_dict = await position_manager.create_position(sample_position_data)
        
        # Verify position is in indexes
        assert 'sig_456' in position_manager.positions_by_signal
        assert 'EURUSD' in position_manager.positions_by_symbol
        
        # Close position
        await position_manager.update_position_state('pos_123', PositionState.CLOSED)
        
        # Verify indexes are cleaned up
        assert 'sig_456' not in position_manager.positions_by_signal
        assert 'EURUSD' not in position_manager.positions_by_symbol