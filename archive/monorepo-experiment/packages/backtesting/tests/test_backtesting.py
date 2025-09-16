"""
Tests for backtesting framework.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from queue import Queue

from fxml4_backtesting import (
    BacktestEngine, EventDrivenEngine, Strategy,
    Portfolio, PerformanceAnalyzer
)
from fxml4_backtesting.strategy import MovingAverageCrossStrategy
from fxml4_backtesting.events import MarketEvent, SignalEvent, OrderEvent, FillEvent


@pytest.fixture
def sample_data():
    """Create sample market data."""
    dates = pd.date_range(start='2023-01-01', end='2023-12-31', freq='D')
    
    # Generate realistic price data
    np.random.seed(42)
    returns = np.random.normal(0.0002, 0.01, len(dates))
    prices = 1.3000 * np.exp(np.cumsum(returns))
    
    data = pd.DataFrame({
        'open': prices * (1 + np.random.uniform(-0.001, 0.001, len(dates))),
        'high': prices * (1 + np.random.uniform(0, 0.005, len(dates))),
        'low': prices * (1 + np.random.uniform(-0.005, 0, len(dates))),
        'close': prices,
        'volume': np.random.uniform(1000, 5000, len(dates))
    }, index=dates)
    
    return data


@pytest.fixture
def multi_symbol_data():
    """Create multi-symbol market data."""
    symbols = ['EURUSD', 'GBPUSD', 'USDJPY']
    data = {}
    
    for i, symbol in enumerate(symbols):
        dates = pd.date_range(start='2023-01-01', end='2023-12-31', freq='D')
        
        # Different characteristics for each pair
        np.random.seed(42 + i)
        volatility = 0.01 * (1 + i * 0.2)  # Increasing volatility
        drift = 0.0001 * (1 - i * 0.5)  # Varying drift
        
        returns = np.random.normal(drift, volatility, len(dates))
        
        if symbol == 'USDJPY':
            prices = 110.0 * np.exp(np.cumsum(returns))
        else:
            prices = 1.3000 * np.exp(np.cumsum(returns))
        
        data[symbol] = pd.DataFrame({
            'open': prices * (1 + np.random.uniform(-0.001, 0.001, len(dates))),
            'high': prices * (1 + np.random.uniform(0, 0.005, len(dates))),
            'low': prices * (1 + np.random.uniform(-0.005, 0, len(dates))),
            'close': prices,
            'volume': np.random.uniform(1000, 5000, len(dates))
        }, index=dates)
    
    return data


class TestStrategy(Strategy):
    """Simple test strategy."""
    
    def calculate_signals(self, event: MarketEvent) -> None:
        """Generate test signals."""
        # Buy every 10 bars, sell every 15 bars
        bar_count = len(self.data_handler.get_all_bars(event.symbol))
        
        if bar_count % 10 == 0 and not self.has_position(event.symbol):
            signal = self.create_signal(
                symbol=event.symbol,
                signal_type='BUY',
                strength=0.8
            )
            self.send_signal(signal)
        
        elif bar_count % 15 == 0 and self.has_position(event.symbol):
            signal = self.create_signal(
                symbol=event.symbol,
                signal_type='SELL',
                strength=0.8
            )
            self.send_signal(signal)


class TestEventDrivenEngine:
    """Test event-driven backtesting engine."""
    
    def test_initialization(self):
        """Test engine initialization."""
        engine = EventDrivenEngine(
            initial_capital=10000,
            commission=0.001,
            slippage_model="fixed"
        )
        
        assert engine.initial_capital == 10000
        assert engine.commission == 0.001
        assert engine.slippage_model == "fixed"
        assert isinstance(engine.events_queue, Queue)
    
    def test_simple_backtest(self, sample_data):
        """Test simple backtest execution."""
        engine = EventDrivenEngine(
            initial_capital=10000,
            commission=0.001
        )
        
        strategy = TestStrategy()
        results = engine.run(strategy, sample_data, symbols=['EURUSD'])
        
        assert 'equity_curve' in results
        assert 'trades' in results
        assert 'metrics' in results
        assert results['final_equity'] > 0
        assert results['event_count'] > 0
    
    def test_moving_average_strategy(self, sample_data):
        """Test MA crossover strategy."""
        engine = EventDrivenEngine(
            initial_capital=10000,
            commission=0.001
        )
        
        strategy = MovingAverageCrossStrategy(
            short_window=10,
            long_window=30
        )
        
        results = engine.run(strategy, sample_data, symbols=['EURUSD'])
        
        # Check results structure
        assert isinstance(results['equity_curve'], pd.DataFrame)
        assert isinstance(results['trades'], pd.DataFrame)
        # metrics can be either dict or PerformanceMetrics object
        assert hasattr(results['metrics'], 'total_return') or isinstance(results['metrics'], dict)
        
        # Should have some trades
        assert len(results['trades']) > 0
    
    def test_multi_symbol_backtest(self, multi_symbol_data):
        """Test multi-symbol backtesting."""
        engine = EventDrivenEngine(
            initial_capital=30000,
            commission=0.001
        )
        
        strategy = MovingAverageCrossStrategy()
        results = engine.run(strategy, multi_symbol_data)
        
        # Should process all symbols
        assert results['event_count'] > len(multi_symbol_data) * 100
        
        # Check positions
        if results['positions']:
            for symbol in results['positions']:
                assert symbol in multi_symbol_data


class TestPortfolio:
    """Test portfolio management."""
    
    def test_portfolio_initialization(self):
        """Test portfolio initialization."""
        events_queue = Queue()
        portfolio = Portfolio(
            initial_capital=10000,
            events_queue=events_queue,
            data_handler=None
        )
        
        assert portfolio.initial_capital == 10000
        assert portfolio.current_capital == 10000
        assert portfolio.equity == 10000
        assert len(portfolio.positions) == 0
    
    def test_position_management(self):
        """Test position tracking."""
        events_queue = Queue()
        portfolio = Portfolio(
            initial_capital=10000,
            events_queue=events_queue,
            data_handler=None
        )
        
        # Simulate market update
        from fxml4_backtesting.events import EventType
        market_event = MarketEvent(
            type=EventType.MARKET,
            timestamp=datetime.now(),
            symbol='EURUSD',
            data=pd.Series({'close': 1.1000, 'volume': 1000})
        )
        portfolio.update_market_data(market_event)
        
        # Simulate fill
        from fxml4_backtesting.events import OrderSide
        fill_event = FillEvent(
            type=EventType.FILL,
            timestamp=datetime.now(),
            symbol='EURUSD',
            order_id='test-001',
            exchange='BACKTEST',
            side=OrderSide.BUY,
            quantity=1000,
            price=1.1000,
            commission=1.10,
            slippage=0.0001
        )
        portfolio.update_fill(fill_event)
        
        # Check position
        assert 'EURUSD' in portfolio.positions
        position = portfolio.positions['EURUSD']
        assert position.quantity == 1000
        assert position.average_price == 1.1000
        
        # Check cash
        expected_cash = 10000 - (1000 * 1.1000 + 1.10)
        assert abs(portfolio.current_capital - expected_cash) < 0.01


class TestPerformanceAnalyzer:
    """Test performance analysis."""
    
    def test_metrics_calculation(self):
        """Test performance metrics calculation."""
        # Create sample equity curve
        dates = pd.date_range('2023-01-01', '2023-12-31', freq='D')
        equity = 10000 * (1 + np.random.normal(0.0002, 0.01, len(dates))).cumprod()
        
        equity_curve = pd.DataFrame({
            'timestamp': dates,
            'equity': equity,
            'returns': np.concatenate([[0], np.diff(equity) / equity[:-1]])
        })
        
        # Create sample trades
        trades = pd.DataFrame({
            'realized_pnl': [100, -50, 200, -30, 150, -80, 300],
            'entry_price': [1.1000, 1.1050, 1.1100, 1.1150, 1.1200, 1.1250, 1.1300],
            'exit_price': [1.1050, 1.1000, 1.1200, 1.1100, 1.1300, 1.1150, 1.1450],
            'quantity': [1000] * 7
        })
        
        analyzer = PerformanceAnalyzer()
        metrics = analyzer.calculate_metrics(
            equity_curve=equity_curve,
            trades=trades,
            initial_capital=10000
        )
        
        # Check metrics exist
        assert hasattr(metrics, 'total_return')
        assert hasattr(metrics, 'sharpe_ratio')
        assert hasattr(metrics, 'max_drawdown')
        assert hasattr(metrics, 'win_rate')
        assert hasattr(metrics, 'profit_factor')
        
        # Check reasonable values
        assert -1 <= metrics.total_return <= 10  # Reasonable return range
        assert -5 <= metrics.sharpe_ratio <= 5  # Reasonable Sharpe range
        assert -1 <= metrics.max_drawdown <= 0  # Drawdown is negative
        assert 0 <= metrics.win_rate <= 1  # Win rate is percentage