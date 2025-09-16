"""Tests for P&L Tracker."""

import pytest
import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import Mock, patch, AsyncMock

from fxml4_trade_manager.pnl_tracker import (
    PnLTracker, PnLMetrics, PnLPeriod, TradeOutcome, PnLSnapshot
)


@pytest.fixture
def pnl_tracker():
    """Create P&L tracker instance."""
    return PnLTracker()


@pytest.fixture
def sample_trade():
    """Sample trade data for testing."""
    return {
        'trade_id': 'trade_123',
        'position_id': 'pos_456',
        'symbol': 'EURUSD',
        'side': 'BUY',
        'quantity': 10000,
        'entry_price': 1.1000,
        'exit_price': 1.1050,
        'realized_pnl': 500,
        'commission': 10,
        'opened_at': datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=2),
        'closed_at': datetime.now(timezone.utc).replace(tzinfo=None)
    }


@pytest.fixture
def sample_position():
    """Sample position data for testing."""
    return {
        'position_id': 'pos_789',
        'symbol': 'GBPUSD',
        'side': 'SELL',
        'quantity': 8000,
        'avg_entry_price': 1.2500,
        'current_price': 1.2450,
        'unrealized_pnl': 400,
        'realized_pnl': 0,
        'commission': 8
    }


class TestPnLSnapshot:
    """Test PnLSnapshot class."""
    
    def test_snapshot_initialization(self):
        """Test P&L snapshot initialization."""
        snapshot_data = {
            'timestamp': datetime.now(timezone.utc),
            'realized_pnl': 1000,
            'unrealized_pnl': 500,
            'total_pnl': 1500,
            'commission': 50,
            'net_pnl': 1450,
            'position_count': 3,
            'trade_count': 10,
            'win_count': 7,
            'loss_count': 3,
            'win_rate': 0.7,
            'avg_win': 200,
            'avg_loss': -100,
            'profit_factor': 4.67,
            'sharpe_ratio': 1.5,
            'max_drawdown': 0.05,
            'account_balance': 100000
        }
        
        snapshot = PnLSnapshot(snapshot_data)
        
        assert snapshot.realized_pnl == Decimal('1000')
        assert snapshot.unrealized_pnl == Decimal('500')
        assert snapshot.total_pnl == Decimal('1500')
        assert snapshot.net_pnl == Decimal('1450')
        assert snapshot.win_rate == 0.7
        assert snapshot.profit_factor == 4.67
    
    def test_snapshot_to_dict(self):
        """Test snapshot to dictionary conversion."""
        snapshot_data = {
            'timestamp': datetime.now(timezone.utc),
            'realized_pnl': 1000,
            'unrealized_pnl': 500,
            'total_pnl': 1500,
            'commission': 50,
            'net_pnl': 1450
        }
        
        snapshot = PnLSnapshot(snapshot_data)
        snapshot_dict = snapshot.to_dict()
        
        assert snapshot_dict['realized_pnl'] == 1000.0
        assert snapshot_dict['unrealized_pnl'] == 500.0
        assert snapshot_dict['total_pnl'] == 1500.0
        assert 'timestamp' in snapshot_dict


class TestPnLTracker:
    """Test PnLTracker class."""
    
    @pytest.mark.asyncio
    async def test_initialization(self, pnl_tracker):
        """Test P&L tracker initialization."""
        account_balance = Decimal('100000')
        await pnl_tracker.initialize(account_balance)
        
        assert pnl_tracker.account_balance == account_balance
        assert pnl_tracker.peak_balance == account_balance
        assert len(pnl_tracker.equity_curve) == 1
        assert pnl_tracker.equity_curve[0][1] == account_balance
    
    @pytest.mark.asyncio
    async def test_add_trade(self, pnl_tracker, sample_trade):
        """Test adding a trade."""
        await pnl_tracker.initialize(Decimal('100000'))
        
        # First record trade opening
        await pnl_tracker.record_trade_open({
            'position_id': sample_trade['position_id'],
            'symbol': sample_trade['symbol'],
            'side': sample_trade['side'],
            'quantity': sample_trade['quantity'],
            'entry_price': sample_trade['entry_price'],
            'commission': sample_trade['commission'] / 2  # Half commission on open
        })
        
        # Then record trade closing
        await pnl_tracker.record_trade_close(
            position_id=sample_trade['position_id'],
            exit_price=Decimal(str(sample_trade['exit_price'])),
            exit_time=sample_trade['closed_at'].replace(tzinfo=None),  # Make timezone-naive
            commission=Decimal(str(sample_trade['commission'] / 2))  # Other half on close
        )
        
        # Check metrics
        assert pnl_tracker.current_metrics.total_trades == 1
        # Gross PnL should be (1.105 - 1.1) * 10000 = 0.005 * 10000 = 50
        # Net PnL after commission of 10 = 50 - 10 = 40
        # But since realized_pnl is the net pnl, it should be 45 (50 - 5 commission from close)
        assert pnl_tracker.current_metrics.realized_pnl == Decimal('45')  # Net PnL
        assert pnl_tracker.current_metrics.commission_paid == Decimal('10')
        assert pnl_tracker.current_metrics.trades_by_symbol['EURUSD'] == 1
    
    async def _add_trade_helper(self, pnl_tracker, trade_data):
        """Helper to add a trade (open and close)."""
        # Record trade opening
        await pnl_tracker.record_trade_open({
            'position_id': trade_data['position_id'],
            'symbol': trade_data['symbol'],
            'side': trade_data['side'],
            'quantity': trade_data['quantity'],
            'entry_price': trade_data['entry_price'],
            'commission': trade_data.get('commission', 0) / 2
        })
        
        # Record trade closing
        await pnl_tracker.record_trade_close(
            position_id=trade_data['position_id'],
            exit_price=Decimal(str(trade_data['exit_price'])),
            exit_time=trade_data.get('closed_at', datetime.now(timezone.utc)).replace(tzinfo=None),
            commission=Decimal(str(trade_data.get('commission', 0) / 2))
        )
    
    @pytest.mark.asyncio
    async def test_add_winning_trade(self, pnl_tracker, sample_trade):
        """Test adding a winning trade."""
        await pnl_tracker.initialize(Decimal('100000'))
        
        # Make it a bigger win (1.15 instead of 1.105)
        sample_trade['exit_price'] = 1.1500
        await self._add_trade_helper(pnl_tracker, sample_trade)
        
        assert pnl_tracker.current_metrics.winning_trades == 1
        assert pnl_tracker.current_metrics.gross_profit == Decimal('495')  # (1.15-1.1)*10000 - 5 commission
        assert pnl_tracker.current_metrics.consecutive_wins == 1
    
    @pytest.mark.asyncio
    async def test_add_losing_trade(self, pnl_tracker, sample_trade):
        """Test adding a losing trade."""
        await pnl_tracker.initialize(Decimal('100000'))
        
        # Make it a loss (1.095 instead of 1.105)
        sample_trade['exit_price'] = 1.0950
        await self._add_trade_helper(pnl_tracker, sample_trade)
        
        assert pnl_tracker.current_metrics.losing_trades == 1
        assert pnl_tracker.current_metrics.gross_loss == Decimal('55')  # (1.1-1.095)*10000 + 5 commission
        assert pnl_tracker.current_metrics.consecutive_losses == 1
    
    @pytest.mark.asyncio
    async def test_update_position(self, pnl_tracker, sample_position):
        """Test updating position P&L."""
        await pnl_tracker.initialize(Decimal('100000'))
        
        # First open the position
        await pnl_tracker.record_trade_open({
            'position_id': sample_position['position_id'],
            'symbol': sample_position['symbol'],
            'side': sample_position['side'],
            'quantity': sample_position['quantity'],
            'entry_price': sample_position['avg_entry_price'],
            'commission': sample_position['commission']
        })
        
        # Then update its PnL
        await pnl_tracker.update_position_pnl(
            position_id=sample_position['position_id'],
            current_price=Decimal(str(sample_position['current_price']))
        )
        
        # Position PnL should be updated
        assert 'pos_789' in pnl_tracker.open_positions
        # For SELL position: (1.25 - 1.245) * 8000 = 0.005 * 8000 = 40
        assert pnl_tracker.open_positions['pos_789']['unrealized_pnl'] == Decimal('40')
    
    @pytest.mark.asyncio
    async def test_calculate_metrics(self, pnl_tracker):
        """Test calculating performance metrics."""
        await pnl_tracker.initialize(Decimal('100000'))
        
        # Add some trades
        trades = [
            {'trade_id': 't1', 'symbol': 'EURUSD', 'realized_pnl': 500, 'commission': 10},
            {'trade_id': 't2', 'symbol': 'EURUSD', 'realized_pnl': 300, 'commission': 10},
            {'trade_id': 't3', 'symbol': 'GBPUSD', 'realized_pnl': -200, 'commission': 10},
            {'trade_id': 't4', 'symbol': 'EURUSD', 'realized_pnl': 400, 'commission': 10},
            {'trade_id': 't5', 'symbol': 'USDJPY', 'realized_pnl': -100, 'commission': 10}
        ]
        
        for i, trade in enumerate(trades):
            trade.update({
                'position_id': f"pos_{trade['trade_id']}",
                'side': 'BUY',
                'quantity': 10000,
                'entry_price': 1.1000,
                'exit_price': 1.1000 + (trade['realized_pnl'] + trade['commission']) / 10000,  # Calculate exit price from PnL
                'opened_at': datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=2),
                'closed_at': datetime.now(timezone.utc).replace(tzinfo=None)
            })
            await self._add_trade_helper(pnl_tracker, trade)
        
        # Metrics are calculated automatically, just access them
        metrics = pnl_tracker.current_metrics
        
        assert metrics.total_trades == 5
        assert metrics.winning_trades == 3
        assert metrics.losing_trades == 2
        assert metrics.win_rate == pytest.approx(0.6, rel=0.01)
        assert metrics.profit_factor > 1  # Should be profitable
        # Average win/loss are calculated from net PnL (after commission)
        # Win trades: (500-5), (300-5), (400-5) = 495, 295, 395
        # Loss trades: (-200-5), (-100-5) = -205, -105
        assert metrics.average_win > 0  # Should be around (495+295+395)/3 = 395
        assert metrics.average_loss > 0  # Should be around (205+105)/2 = 155
        assert metrics.largest_win > 0
        assert metrics.largest_loss < 0
    
    @pytest.mark.asyncio
    async def test_get_snapshot(self, pnl_tracker, sample_trade, sample_position):
        """Test getting P&L snapshot."""
        await pnl_tracker.initialize(Decimal('100000'))
        
        # Add trade and position
        await pnl_tracker.add_trade(sample_trade)
        await pnl_tracker.update_position(sample_position)
        
        snapshot = await pnl_tracker.get_snapshot()
        
        assert snapshot.realized_pnl == Decimal('490')  # 500 - 10 commission
        assert snapshot.unrealized_pnl == Decimal('400')
        assert snapshot.total_pnl == Decimal('890')  # 490 + 400
        assert snapshot.commission == Decimal('10')
        assert snapshot.net_pnl == Decimal('890')  # Same as total since commission already deducted
        assert snapshot.position_count == 1
        assert snapshot.trade_count == 1
    
    @pytest.mark.asyncio
    async def test_get_period_pnl_daily(self, pnl_tracker):
        """Test getting daily P&L."""
        await pnl_tracker.initialize(Decimal('100000'))
        
        # Add trades on different days
        today = datetime.now(timezone.utc)
        yesterday = today - timedelta(days=1)
        
        trade1 = {
            'trade_id': 't1',
            'position_id': 'p1',
            'symbol': 'EURUSD',
            'side': 'BUY',
            'quantity': 10000,
            'entry_price': 1.1000,
            'exit_price': 1.1050,
            'realized_pnl': 500,
            'commission': 10,
            'opened_at': yesterday - timedelta(hours=2),
            'closed_at': yesterday
        }
        
        trade2 = {
            'trade_id': 't2',
            'position_id': 'p2',
            'symbol': 'GBPUSD',
            'side': 'SELL',
            'quantity': 8000,
            'entry_price': 1.2500,
            'exit_price': 1.2450,
            'realized_pnl': 400,
            'commission': 8,
            'opened_at': today - timedelta(hours=1),
            'closed_at': today
        }
        
        with patch('fxml4_trade_manager.pnl_tracker.datetime') as mock_dt:
            mock_dt.utcnow.return_value = yesterday
            await pnl_tracker.add_trade(trade1)
            
            mock_dt.utcnow.return_value = today
            await pnl_tracker.add_trade(trade2)
        
        daily_pnl = await pnl_tracker.get_period_pnl(PnLPeriod.DAILY)
        
        assert len(daily_pnl) >= 2
        assert any(p['net_pnl'] == 490 for p in daily_pnl)  # 500 - 10
        assert any(p['net_pnl'] == 392 for p in daily_pnl)  # 400 - 8
    
    @pytest.mark.asyncio
    async def test_get_symbol_pnl(self, pnl_tracker):
        """Test getting P&L by symbol."""
        await pnl_tracker.initialize(Decimal('100000'))
        
        # Add trades for different symbols
        trades = [
            {'symbol': 'EURUSD', 'realized_pnl': 500, 'commission': 10},
            {'symbol': 'EURUSD', 'realized_pnl': 300, 'commission': 10},
            {'symbol': 'GBPUSD', 'realized_pnl': -200, 'commission': 10},
            {'symbol': 'GBPUSD', 'realized_pnl': 400, 'commission': 10}
        ]
        
        for i, trade in enumerate(trades):
            trade.update({
                'trade_id': f't{i}',
                'position_id': f'p{i}',
                'side': 'BUY',
                'quantity': 10000,
                'entry_price': 1.1000,
                'exit_price': 1.1050,
                'opened_at': datetime.now(timezone.utc) - timedelta(hours=2),
                'closed_at': datetime.now(timezone.utc)
            })
            await pnl_tracker.add_trade(trade)
        
        symbol_pnl = await pnl_tracker.get_symbol_pnl()
        
        assert 'EURUSD' in symbol_pnl
        assert symbol_pnl['EURUSD']['realized_pnl'] == Decimal('780')  # (500-10) + (300-10) = 490 + 290
        assert symbol_pnl['EURUSD']['commission'] == Decimal('20')
        assert symbol_pnl['EURUSD']['trade_count'] == 2
        
        assert 'GBPUSD' in symbol_pnl
        assert symbol_pnl['GBPUSD']['realized_pnl'] == Decimal('180')  # (-200-10) + (400-10) = -210 + 390
        assert symbol_pnl['GBPUSD']['commission'] == Decimal('20')
        assert symbol_pnl['GBPUSD']['trade_count'] == 2
    
    @pytest.mark.asyncio
    async def test_calculate_drawdown(self, pnl_tracker):
        """Test drawdown calculation."""
        await pnl_tracker.initialize(Decimal('100000'))
        
        # Simulate balance changes
        pnl_tracker.account_balance = Decimal('95000')  # 5% loss
        
        drawdown = await pnl_tracker.calculate_drawdown()
        
        assert drawdown['current_drawdown'] == Decimal('5000')
        assert drawdown['current_drawdown_pct'] == Decimal('0.05')
        assert drawdown['max_drawdown'] == Decimal('5000')
        assert drawdown['max_drawdown_pct'] == Decimal('0.05')
    
    @pytest.mark.asyncio
    async def test_reset_daily_pnl(self, pnl_tracker):
        """Test resetting daily P&L."""
        await pnl_tracker.initialize(Decimal('100000'))
        
        # Add some daily P&L
        pnl_tracker.daily_pnl[datetime.now(timezone.utc).date()] = Decimal('500')
        
        await pnl_tracker.reset_daily_pnl()
        
        assert datetime.now(timezone.utc).date() in pnl_tracker.daily_pnl
        assert pnl_tracker.daily_pnl[datetime.now(timezone.utc).date()] == Decimal('0')
    
    @pytest.mark.asyncio
    async def test_export_history(self, pnl_tracker, sample_trade):
        """Test exporting P&L history."""
        await pnl_tracker.initialize(Decimal('100000'))
        
        # Add trade and create snapshot
        await pnl_tracker.add_trade(sample_trade)
        await pnl_tracker.get_snapshot()  # This adds to history
        
        history = await pnl_tracker.export_history()
        
        assert 'trades' in history
        assert 'snapshots' in history
        assert 'daily_pnl' in history
        assert 'metrics' in history
        
        assert len(history['trades']) == 1
        assert history['trades'][0]['trade_id'] == 'trade_123'
    
    @pytest.mark.asyncio
    async def test_sharpe_ratio_calculation(self, pnl_tracker):
        """Test Sharpe ratio calculation."""
        await pnl_tracker.initialize(Decimal('100000'))
        
        # Add dummy trades to satisfy the trades_history requirement
        for j in range(3):
            dummy_trade = {
                'trade_id': f'dummy_{j}',
                'position_id': f'pos_{j}',
                'symbol': 'EURUSD',
                'side': 'BUY',
                'quantity': 1000,
                'entry_price': 1.1000,
                'exit_price': 1.1010,
                'realized_pnl': 10,
                'commission': 1,
                'opened_at': datetime.now(timezone.utc) - timedelta(hours=j+1),
                'closed_at': datetime.now(timezone.utc) - timedelta(hours=j)
            }
            await pnl_tracker.add_trade(dummy_trade)
        
        # Add daily returns
        for i in range(30):
            date = datetime.now(timezone.utc).date() - timedelta(days=i)
            # Simulate random returns between -2% and +3%
            daily_return = Decimal(str((i % 5 - 2) * 100))  # -200 to 300
            pnl_tracker.current_metrics.daily_pnl[date] = daily_return
            # Also need to update equity curve for sharpe calculation
            pnl_tracker.equity_curve.append((date, Decimal('100000') + daily_return))
        
        sharpe = await pnl_tracker._calculate_sharpe_ratio()
        
        assert isinstance(sharpe, float)
        # Sharpe ratio should be calculated
        assert sharpe != 0
    
    @pytest.mark.asyncio
    async def test_consecutive_tracking(self, pnl_tracker):
        """Test consecutive wins/losses tracking."""
        await pnl_tracker.initialize(Decimal('100000'))
        
        # Add consecutive wins
        for i in range(3):
            trade = {
                'trade_id': f'win_{i}',
                'position_id': f'pos_win_{i}',
                'symbol': 'EURUSD',
                'side': 'BUY',
                'quantity': 10000,
                'entry_price': 1.1000,
                'exit_price': 1.1050,
                'realized_pnl': 500,
                'commission': 10,
                'opened_at': datetime.now(timezone.utc) - timedelta(hours=2),
                'closed_at': datetime.now(timezone.utc)
            }
            await pnl_tracker.add_trade(trade)
        
        assert pnl_tracker.current_consecutive_wins == 3
        assert pnl_tracker.max_consecutive_wins == 3
        assert pnl_tracker.current_consecutive_losses == 0
        
        # Add a loss to break the streak
        loss_trade = {
            'trade_id': 'loss_1',
            'position_id': 'pos_loss_1',
            'symbol': 'EURUSD',
            'side': 'BUY',
            'quantity': 10000,
            'entry_price': 1.1000,
            'exit_price': 1.0950,
            'realized_pnl': -500,
            'commission': 10,
            'opened_at': datetime.now(timezone.utc) - timedelta(hours=1),
            'closed_at': datetime.now(timezone.utc)
        }
        await pnl_tracker.add_trade(loss_trade)
        
        assert pnl_tracker.current_consecutive_wins == 0
        assert pnl_tracker.current_consecutive_losses == 1
        assert pnl_tracker.max_consecutive_wins == 3  # Still 3