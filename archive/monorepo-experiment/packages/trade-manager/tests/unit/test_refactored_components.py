"""Unit tests demonstrating the refactored Trade Manager components."""

import pytest
from decimal import Decimal
from datetime import datetime, timedelta

from fxml4_trade_manager import (
    # Core Components
    PositionManager, RiskMonitor, PnLTracker, ExitStrategyManager,
    
    # Domain Models
    OrderSide, TradeData, AccountData, MarketData,
    
    # Test Implementations
    MockTimeProvider, MockEventPublisher, InMemoryMetricsCollector,
    MockMarketDataProvider, MockBrokerAdapter
)


class TestPositionManagerWithDependencyInjection:
    """Test PositionManager with injected dependencies."""
    
    @pytest.fixture
    def time_provider(self):
        """Create a mock time provider."""
        return MockTimeProvider(datetime(2024, 1, 1, 12, 0, 0))
    
    @pytest.fixture
    def event_publisher(self):
        """Create a mock event publisher."""
        return MockEventPublisher()
    
    @pytest.fixture
    def metrics_collector(self):
        """Create a metrics collector."""
        return InMemoryMetricsCollector()
    
    @pytest.fixture
    def position_manager(self, time_provider, event_publisher, metrics_collector):
        """Create position manager with injected dependencies."""
        return PositionManager(
            time_provider=time_provider,
            event_publisher=event_publisher,
            metrics_collector=metrics_collector
        )
    
    @pytest.mark.asyncio
    async def test_create_position_with_injected_time(self, position_manager, time_provider):
        """Test position creation uses injected time provider."""
        position_data = {
            'position_id': 'POS_001',
            'symbol': 'EURUSD',
            'side': 'BUY',
            'target_quantity': '10000'
        }
        
        position = await position_manager.create_position(position_data)
        
        assert position['position_id'] == 'POS_001'
        assert position['created_at'] == time_provider.now().isoformat()
    
    @pytest.mark.asyncio
    async def test_position_events_published(self, position_manager, event_publisher):
        """Test that position events are published."""
        position_data = {
            'position_id': 'POS_002',
            'symbol': 'GBPUSD',
            'side': 'SELL',
            'target_quantity': '5000'
        }
        
        await position_manager.create_position(position_data)
        
        events = event_publisher.get_events('position.created')
        assert len(events) == 1
        assert events[0][1]['position_id'] == 'POS_002'


class TestRiskMonitorWithDependencyInjection:
    """Test RiskMonitor with injected dependencies."""
    
    @pytest.fixture
    def time_provider(self):
        """Create a mock time provider."""
        return MockTimeProvider(datetime(2024, 1, 1, 12, 0, 0))
    
    @pytest.fixture
    def market_data_provider(self):
        """Create a mock market data provider."""
        return MockMarketDataProvider()
    
    @pytest.fixture
    def risk_monitor(self, time_provider):
        """Create risk monitor with injected dependencies."""
        return RiskMonitor(time_provider=time_provider)
    
    @pytest.mark.asyncio
    async def test_check_pre_trade_risk_with_small_methods(self, risk_monitor):
        """Test pre-trade risk checking with refactored small methods."""
        trade_request = TradeData(
            symbol='EURUSD',
            side=OrderSide.BUY,
            quantity=Decimal('10000'),  # Smaller position: $10,850
            price=Decimal('1.0850'),
            stop_loss=Decimal('1.0800')
        )
        
        account_data = AccountData(
            balance=Decimal('100000'),  # Larger account
            equity=Decimal('100000')
        )
        
        positions = []
        
        # Initialize risk monitor with reasonable limits
        await risk_monitor.initialize({
            'max_position_size': 20000,  # $20K max position value
            'max_positions': 10,
            'max_risk_per_trade': 0.05,  # 5% risk per trade
            'daily_loss_limit': 0.10,   # 10% daily loss limit
            'max_exposure': 0.50,        # 50% max exposure
            'max_volatility_exposure': 500.0  # High volatility limit for test
        })
        
        # Check pre-trade risk
        allowed, violations = await risk_monitor.check_pre_trade_risk(
            trade_request,
            account_data,
            positions
        )
        
        assert allowed is True
        assert len(violations) == 0
    
    @pytest.mark.asyncio
    async def test_risk_violations_recorded(self, risk_monitor):
        """Test that risk violations are properly recorded."""
        metrics_collector = InMemoryMetricsCollector()
        monitor = RiskMonitor(
            time_provider=MockTimeProvider(),
            metrics_collector=metrics_collector
        )
        
        # Create a trade that violates position size
        trade_request = TradeData(
            symbol='EURUSD',
            side=OrderSide.BUY,
            quantity=Decimal('1000000'),  # Very large position
            price=Decimal('1.0850')
        )
        
        account_data = AccountData(balance=Decimal('10000'))
        
        await monitor.initialize({'max_position_size': 10000})
        
        allowed, violations = await monitor.check_pre_trade_risk(
            trade_request,
            account_data,
            []
        )
        
        assert allowed is False
        assert len(violations) > 0
        assert len(metrics_collector.risk_violations) > 0


class TestPnLTrackerWithDependencyInjection:
    """Test PnLTracker with injected dependencies."""
    
    @pytest.fixture
    def time_provider(self):
        """Create a mock time provider."""
        return MockTimeProvider(datetime(2024, 1, 1, 12, 0, 0))
    
    @pytest.fixture
    def pnl_tracker(self, time_provider):
        """Create P&L tracker with injected dependencies."""
        event_publisher = MockEventPublisher()
        metrics_collector = InMemoryMetricsCollector()
        
        return PnLTracker(
            time_provider=time_provider,
            event_publisher=event_publisher,
            metrics_collector=metrics_collector
        )
    
    @pytest.mark.asyncio
    async def test_trade_timing_uses_injected_time(self, pnl_tracker, time_provider):
        """Test that trade timing uses injected time provider."""
        await pnl_tracker.initialize(Decimal('100000'))
        
        trade_data = {
            'position_id': 'POS_001',
            'symbol': 'EURUSD',
            'side': 'BUY',
            'quantity': '10000',
            'entry_price': '1.0850'
        }
        
        await pnl_tracker.record_trade_open(trade_data)
        
        # Advance time
        time_provider.advance_time(3600)  # 1 hour
        
        # Close trade
        await pnl_tracker.record_trade_close(
            'POS_001',
            Decimal('1.0900'),
            commission=Decimal('10')
        )
        
        # Check that duration is calculated correctly
        assert len(pnl_tracker.trades_history) == 1
        trade = pnl_tracker.trades_history[0]
        assert trade['duration'] == 60  # 60 minutes


class TestExitStrategyManagerWithDependencyInjection:
    """Test ExitStrategyManager with injected dependencies."""
    
    @pytest.fixture
    def exit_manager(self):
        """Create exit strategy manager with injected dependencies."""
        return ExitStrategyManager(
            time_provider=MockTimeProvider(),
            event_publisher=MockEventPublisher()
        )
    
    @pytest.fixture
    def broker_adapter(self):
        """Create mock broker adapter."""
        return MockBrokerAdapter()
    
    @pytest.mark.asyncio
    async def test_time_based_exits_use_injected_time(self, exit_manager):
        """Test time-based exits use injected time provider."""
        # Assign scalping strategy with time exits
        await exit_manager.assign_strategy('POS_001', 'scalping')
        
        # Create position opened 2 hours ago
        time_provider = MockTimeProvider(datetime(2024, 1, 1, 10, 0, 0))
        exit_manager._time_provider = time_provider
        
        position_data = {
            'position_id': 'POS_001',
            'opened_at': datetime(2024, 1, 1, 8, 0, 0)  # 2 hours ago
        }
        
        should_exit, reason = await exit_manager.check_time_exits(position_data)
        
        assert should_exit is True
        assert reason == 'time_exit'
    
    @pytest.mark.asyncio
    async def test_exit_levels_calculation(self, exit_manager):
        """Test exit levels calculation with market data."""
        position_data = {
            'position_id': 'POS_001',
            'symbol': 'EURUSD',
            'side': 'BUY',
            'entry_price': '1.0850'
        }
        
        market_data = MarketData(
            symbol='EURUSD',
            current_price=Decimal('1.0850'),
            atr=Decimal('0.0050')
        )
        
        await exit_manager.assign_strategy('POS_001', 'conservative')
        levels = await exit_manager.calculate_exit_levels(position_data, market_data)
        
        assert 'stop_loss' in levels
        assert 'take_profit_1' in levels
        assert levels['stop_loss'] < Decimal('1.0850')  # Below entry for buy
        assert levels['take_profit_1'] > Decimal('1.0850')  # Above entry for buy


@pytest.mark.asyncio
async def test_integration_with_all_components():
    """Test integration of all refactored components."""
    # Create shared dependencies
    time_provider = MockTimeProvider(datetime(2024, 1, 1, 12, 0, 0))
    event_publisher = MockEventPublisher()
    metrics_collector = InMemoryMetricsCollector()
    market_data_provider = MockMarketDataProvider()
    
    # Create all managers with shared dependencies
    position_manager = PositionManager(
        time_provider=time_provider,
        event_publisher=event_publisher,
        metrics_collector=metrics_collector
    )
    
    risk_monitor = RiskMonitor(
        time_provider=time_provider,
        event_publisher=event_publisher,
        metrics_collector=metrics_collector,
        market_data_provider=market_data_provider
    )
    
    pnl_tracker = PnLTracker(
        time_provider=time_provider,
        event_publisher=event_publisher,
        metrics_collector=metrics_collector
    )
    
    exit_manager = ExitStrategyManager(
        time_provider=time_provider,
        event_publisher=event_publisher
    )
    
    # Initialize components
    await risk_monitor.initialize({'max_positions': 5})
    await pnl_tracker.initialize(Decimal('100000'))
    
    # Create a position
    position_data = {
        'position_id': 'POS_001',
        'symbol': 'EURUSD',
        'side': 'BUY',
        'target_quantity': '10000',
        'entry_price': '1.0850'
    }
    
    position = await position_manager.create_position(position_data)
    
    # Check events were published
    events = event_publisher.get_events()
    assert len(events) > 0
    assert any(e[0] == 'position.created' for e in events)
    
    # Verify all components are working with injected dependencies
    assert position['created_at'] == time_provider.now().isoformat()
    
    # Get metrics summary
    metrics_summary = metrics_collector.get_metrics_summary()
    assert metrics_summary['total_trades'] == 0  # No trades closed yet