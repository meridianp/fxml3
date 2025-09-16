"""
Backtesting engines for FXML4.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union, Callable
from queue import Queue, Empty
import pandas as pd
import numpy as np
from dataclasses import dataclass
from enum import Enum

from fxml4_core.logging import get_logger
from fxml4_backtesting.events import (
    Event, EventType, MarketEvent, SignalEvent, 
    OrderEvent, FillEvent
)
from fxml4_backtesting.portfolio import Portfolio
from fxml4_backtesting.execution import ExecutionHandler
from fxml4_backtesting.strategy import Strategy

logger = get_logger(__name__)


class BacktestEngine(ABC):
    """Abstract base class for backtesting engines."""
    
    def __init__(
        self,
        initial_capital: float = 10000.0,
        commission: float = 0.001,
        slippage_model: str = "fixed",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ):
        self.initial_capital = initial_capital
        self.commission = commission
        self.slippage_model = slippage_model
        self.start_date = start_date
        self.end_date = end_date
        self.results = None
    
    @abstractmethod
    def run(
        self,
        strategy: Strategy,
        data: pd.DataFrame,
        symbols: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Run backtest."""
        pass
    
    @abstractmethod
    def get_results(self) -> Dict[str, Any]:
        """Get backtest results."""
        pass


class EventDrivenEngine(BacktestEngine):
    """Event-driven backtesting engine."""
    
    def __init__(
        self,
        initial_capital: float = 10000.0,
        commission: float = 0.001,
        slippage_model: str = "fixed",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        heartbeat: float = 0.0,
        max_events: int = 1000000
    ):
        super().__init__(
            initial_capital=initial_capital,
            commission=commission,
            slippage_model=slippage_model,
            start_date=start_date,
            end_date=end_date
        )
        
        self.heartbeat = heartbeat
        self.max_events = max_events
        self.events_queue = Queue()
        self.data_handler = None
        self.portfolio = None
        self.execution_handler = None
        self.strategy = None
        
        self._continue_backtest = True
        self._event_count = 0
        
    def run(
        self,
        strategy: Strategy,
        data: Union[pd.DataFrame, Dict[str, pd.DataFrame]],
        symbols: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Run event-driven backtest."""
        logger.info("Starting event-driven backtest")
        
        # Initialize components
        self._initialize_components(strategy, data, symbols)
        
        # Main event loop
        while self._continue_backtest:
            try:
                # Get next event with timeout
                event = self.events_queue.get(timeout=self.heartbeat)
                
                if event is not None:
                    self._process_event(event)
                    self._event_count += 1
                    
                    if self._event_count >= self.max_events:
                        logger.warning("Maximum events reached, stopping backtest")
                        break
                
            except Empty:
                # No events in queue, check if more data
                if not self.data_handler.continue_backtest:
                    self._continue_backtest = False
                else:
                    # Generate new market event
                    self.data_handler.update_bars()
        
        # Generate results
        self.results = self._generate_results()
        logger.info("Backtest complete - processed %d events", self._event_count)
        
        return self.results
    
    def _initialize_components(
        self,
        strategy: Strategy,
        data: Union[pd.DataFrame, Dict[str, pd.DataFrame]],
        symbols: Optional[List[str]] = None
    ) -> None:
        """Initialize backtest components."""
        # Create data handler
        from fxml4_backtesting.data import DataHandler
        self.data_handler = DataHandler(
            data=data,
            events_queue=self.events_queue,
            symbols=symbols,
            start_date=self.start_date,
            end_date=self.end_date
        )
        
        # Create portfolio
        self.portfolio = Portfolio(
            initial_capital=self.initial_capital,
            events_queue=self.events_queue,
            data_handler=self.data_handler
        )
        
        # Create execution handler
        self.execution_handler = ExecutionHandler(
            events_queue=self.events_queue,
            portfolio=self.portfolio,
            commission=self.commission,
            slippage_model=self.slippage_model
        )
        
        # Set strategy
        self.strategy = strategy
        self.strategy.set_components(
            data_handler=self.data_handler,
            portfolio=self.portfolio,
            events_queue=self.events_queue
        )
        
        logger.info("Initialized backtest components")
    
    def _process_event(self, event: Event) -> None:
        """Process a single event."""
        if event.type == EventType.MARKET:
            # Update portfolio with new market data
            self.portfolio.update_market_data(event)
            
            # Generate signals from strategy
            self.strategy.calculate_signals(event)
            
        elif event.type == EventType.SIGNAL:
            # Generate orders from signals
            self.portfolio.update_signal(event)
            
        elif event.type == EventType.ORDER:
            # Execute orders
            self.execution_handler.execute_order(event)
            
        elif event.type == EventType.FILL:
            # Update portfolio with fills
            self.portfolio.update_fill(event)
    
    def _generate_results(self) -> Dict[str, Any]:
        """Generate backtest results."""
        # Get portfolio history
        equity_curve = pd.DataFrame(self.portfolio.equity_curve)
        trades = pd.DataFrame(self.portfolio.closed_positions)
        
        # Calculate performance metrics
        from fxml4_backtesting.performance import PerformanceAnalyzer
        analyzer = PerformanceAnalyzer()
        metrics = analyzer.calculate_metrics(
            equity_curve=equity_curve,
            trades=trades,
            initial_capital=self.initial_capital
        )
        
        return {
            "equity_curve": equity_curve,
            "trades": trades,
            "metrics": metrics,
            "final_equity": self.portfolio.equity,
            "total_return": (self.portfolio.equity - self.initial_capital) / self.initial_capital,
            "event_count": self._event_count,
            "positions": self.portfolio.positions
        }
    
    def get_results(self) -> Dict[str, Any]:
        """Get backtest results."""
        if self.results is None:
            raise ValueError("No results available. Run backtest first.")
        return self.results


class VectorizedEngine(BacktestEngine):
    """Vectorized backtesting engine for faster execution."""
    
    def __init__(
        self,
        initial_capital: float = 10000.0,
        commission: float = 0.001,
        slippage: float = 0.0001,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ):
        super().__init__(
            initial_capital=initial_capital,
            commission=commission,
            slippage_model="fixed",
            start_date=start_date,
            end_date=end_date
        )
        self.slippage = slippage
    
    def run(
        self,
        strategy: Strategy,
        data: pd.DataFrame,
        symbols: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Run vectorized backtest."""
        logger.info("Starting vectorized backtest")
        
        # Filter data by date range
        if self.start_date:
            data = data[data.index >= self.start_date]
        if self.end_date:
            data = data[data.index <= self.end_date]
        
        # Generate signals
        signals = strategy.generate_signals(data)
        
        # Calculate positions
        positions = self._calculate_positions(signals)
        
        # Calculate returns
        returns = self._calculate_returns(data, positions)
        
        # Calculate equity curve
        equity_curve = self._calculate_equity_curve(returns)
        
        # Extract trades
        trades = self._extract_trades(positions, data)
        
        # Calculate metrics
        from fxml4_backtesting.performance import PerformanceAnalyzer
        analyzer = PerformanceAnalyzer()
        metrics = analyzer.calculate_metrics(
            equity_curve=equity_curve,
            trades=trades,
            initial_capital=self.initial_capital
        )
        
        self.results = {
            "equity_curve": equity_curve,
            "trades": trades,
            "metrics": metrics,
            "signals": signals,
            "positions": positions,
            "returns": returns
        }
        
        logger.info("Vectorized backtest complete")
        return self.results
    
    def _calculate_positions(self, signals: pd.DataFrame) -> pd.DataFrame:
        """Calculate positions from signals."""
        # Simple position calculation - can be overridden
        positions = signals.copy()
        
        # Apply position sizing
        positions = positions.fillna(0)
        
        return positions
    
    def _calculate_returns(
        self,
        data: pd.DataFrame,
        positions: pd.DataFrame
    ) -> pd.DataFrame:
        """Calculate returns from positions."""
        # Calculate price returns
        price_returns = data['close'].pct_change()
        
        # Calculate strategy returns
        strategy_returns = positions.shift(1) * price_returns
        
        # Apply transaction costs
        position_changes = positions.diff().abs()
        costs = position_changes * (self.commission + self.slippage)
        
        # Net returns
        net_returns = strategy_returns - costs
        
        return net_returns
    
    def _calculate_equity_curve(self, returns: pd.DataFrame) -> pd.DataFrame:
        """Calculate equity curve from returns."""
        if isinstance(returns, pd.Series):
            returns = returns.to_frame('returns')
        
        # Calculate cumulative returns
        cum_returns = (1 + returns).cumprod()
        
        # Calculate equity
        equity = self.initial_capital * cum_returns
        
        # Create equity curve dataframe
        equity_curve = pd.DataFrame({
            'timestamp': returns.index,
            'equity': equity.values.flatten(),
            'returns': returns.values.flatten(),
            'drawdown': 0.0  # Will be calculated by performance analyzer
        })
        
        return equity_curve
    
    def _extract_trades(
        self,
        positions: pd.DataFrame,
        data: pd.DataFrame
    ) -> pd.DataFrame:
        """Extract individual trades from positions."""
        trades = []
        
        # Simple trade extraction - can be enhanced
        position_changes = positions.diff()
        
        for idx in position_changes.index:
            change = position_changes.loc[idx]
            
            if isinstance(change, pd.Series):
                change = change.iloc[0]
            
            if change != 0:
                trade = {
                    'timestamp': idx,
                    'symbol': 'default',
                    'side': 'buy' if change > 0 else 'sell',
                    'quantity': abs(change),
                    'price': data.loc[idx, 'close'],
                    'commission': self.commission * abs(change) * data.loc[idx, 'close']
                }
                trades.append(trade)
        
        return pd.DataFrame(trades)
    
    def get_results(self) -> Dict[str, Any]:
        """Get backtest results."""
        if self.results is None:
            raise ValueError("No results available. Run backtest first.")
        return self.results