"""P&L Tracker - Tracks realized and unrealized P&L with detailed analytics."""

from typing import Dict, Any, List, Optional, Tuple, Union
from datetime import timedelta, date, datetime
from decimal import Decimal
import asyncio
import logging
from enum import Enum
from collections import defaultdict
import json

from .domain import (
    ITimeProvider, IPnLTracker, IEventPublisher,
    IMetricsCollector, UTCTimeProvider
)

logger = logging.getLogger(__name__)


class PnLPeriod(str, Enum):
    """P&L calculation periods."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"
    ALL_TIME = "all_time"


class TradeOutcome(str, Enum):
    """Trade outcome classification."""
    WIN = "win"
    LOSS = "loss"
    BREAKEVEN = "breakeven"
    OPEN = "open"


class PnLSnapshot:
    """Point-in-time snapshot of P&L metrics."""
    
    def __init__(self, snapshot_data: Dict[str, Any]):
        self.timestamp = snapshot_data['timestamp']
        self.realized_pnl = Decimal(str(snapshot_data.get('realized_pnl', 0)))
        self.unrealized_pnl = Decimal(str(snapshot_data.get('unrealized_pnl', 0)))
        self.total_pnl = Decimal(str(snapshot_data.get('total_pnl', 0)))
        self.commission = Decimal(str(snapshot_data.get('commission', 0)))
        self.net_pnl = Decimal(str(snapshot_data.get('net_pnl', 0)))
        self.position_count = snapshot_data.get('position_count', 0)
        self.trade_count = snapshot_data.get('trade_count', 0)
        self.win_count = snapshot_data.get('win_count', 0)
        self.loss_count = snapshot_data.get('loss_count', 0)
        self.win_rate = snapshot_data.get('win_rate', 0.0)
        self.avg_win = Decimal(str(snapshot_data.get('avg_win', 0)))
        self.avg_loss = Decimal(str(snapshot_data.get('avg_loss', 0)))
        self.profit_factor = snapshot_data.get('profit_factor', 0.0)
        self.sharpe_ratio = snapshot_data.get('sharpe_ratio', 0.0)
        self.max_drawdown = Decimal(str(snapshot_data.get('max_drawdown', 0)))
        self.account_balance = Decimal(str(snapshot_data.get('account_balance', 0)))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert snapshot to dictionary."""
        return {
            'timestamp': self.timestamp.isoformat() if hasattr(self.timestamp, 'isoformat') else str(self.timestamp),
            'realized_pnl': float(self.realized_pnl),
            'unrealized_pnl': float(self.unrealized_pnl),
            'total_pnl': float(self.total_pnl),
            'commission': float(self.commission),
            'net_pnl': float(self.net_pnl),
            'position_count': self.position_count,
            'trade_count': self.trade_count,
            'win_count': self.win_count,
            'loss_count': self.loss_count,
            'win_rate': self.win_rate,
            'avg_win': float(self.avg_win),
            'avg_loss': float(self.avg_loss),
            'profit_factor': self.profit_factor,
            'sharpe_ratio': self.sharpe_ratio,
            'max_drawdown': float(self.max_drawdown),
            'account_balance': float(self.account_balance)
        }


class PnLMetrics:
    """Comprehensive P&L metrics."""
    
    def __init__(self):
        self.realized_pnl = Decimal('0')
        self.unrealized_pnl = Decimal('0')
        self.gross_profit = Decimal('0')
        self.gross_loss = Decimal('0')
        self.commission_paid = Decimal('0')
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.breakeven_trades = 0
        self.largest_win = Decimal('0')
        self.largest_loss = Decimal('0')
        self.consecutive_wins = 0
        self.consecutive_losses = 0
        self.max_consecutive_wins = 0
        self.max_consecutive_losses = 0
        self.average_win = Decimal('0')
        self.average_loss = Decimal('0')
        self.win_rate = 0.0
        self.profit_factor = 0.0
        self.expectancy = Decimal('0')
        self.sharpe_ratio = 0.0
        self.sortino_ratio = 0.0
        self.max_drawdown = Decimal('0')
        self.max_drawdown_duration = timedelta()
        self.current_drawdown = Decimal('0')
        self.peak_balance = Decimal('0')
        self.roi = 0.0
        self.trades_by_symbol: Dict[str, int] = defaultdict(int)
        self.pnl_by_symbol: Dict[str, Decimal] = defaultdict(Decimal)
        self.pnl_by_strategy: Dict[str, Decimal] = defaultdict(Decimal)
        self.daily_pnl: Dict[date, Decimal] = defaultdict(Decimal)
        self.hourly_pnl: Dict[int, Decimal] = defaultdict(Decimal)
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            'realized_pnl': float(self.realized_pnl),
            'unrealized_pnl': float(self.unrealized_pnl),
            'total_pnl': float(self.realized_pnl + self.unrealized_pnl),
            'gross_profit': float(self.gross_profit),
            'gross_loss': float(self.gross_loss),
            'commission_paid': float(self.commission_paid),
            'net_profit': float(self.realized_pnl - self.commission_paid),
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'breakeven_trades': self.breakeven_trades,
            'largest_win': float(self.largest_win),
            'largest_loss': float(self.largest_loss),
            'consecutive_wins': self.consecutive_wins,
            'consecutive_losses': self.consecutive_losses,
            'max_consecutive_wins': self.max_consecutive_wins,
            'max_consecutive_losses': self.max_consecutive_losses,
            'average_win': float(self.average_win),
            'average_loss': float(self.average_loss),
            'win_rate': self.win_rate,
            'profit_factor': self.profit_factor,
            'expectancy': float(self.expectancy),
            'sharpe_ratio': self.sharpe_ratio,
            'sortino_ratio': self.sortino_ratio,
            'max_drawdown': float(self.max_drawdown),
            'max_drawdown_duration_days': self.max_drawdown_duration.days,
            'current_drawdown': float(self.current_drawdown),
            'roi': self.roi,
            'trades_by_symbol': dict(self.trades_by_symbol),
            'pnl_by_symbol': {k: float(v) for k, v in self.pnl_by_symbol.items()},
            'pnl_by_strategy': {k: float(v) for k, v in self.pnl_by_strategy.items()}
        }


class PnLTracker(IPnLTracker):
    """Tracks and analyzes P&L across all trading activities."""
    
    def __init__(
        self,
        time_provider: Optional[ITimeProvider] = None,
        event_publisher: Optional[IEventPublisher] = None,
        metrics_collector: Optional[IMetricsCollector] = None
    ):
        self._time_provider = time_provider or UTCTimeProvider()
        self._event_publisher = event_publisher
        self._metrics_collector = metrics_collector
        
        self.trades_history: List[Dict[str, Any]] = []
        self.open_positions: Dict[str, Dict[str, Any]] = {}
        self.daily_metrics: Dict[date, PnLMetrics] = {}
        self.period_metrics: Dict[PnLPeriod, PnLMetrics] = {
            period: PnLMetrics() for period in PnLPeriod
        }
        self.current_metrics = PnLMetrics()
        self.account_balance = Decimal('100000')  # Default starting balance
        self.peak_balance = Decimal('100000')
        self.equity_curve: List[Tuple[Any, Decimal]] = []
        self.drawdown_periods: List[Dict[str, Any]] = []
        self._lock = asyncio.Lock()
    
    @property
    def daily_pnl(self) -> Dict[date, Decimal]:
        """Get daily P&L dictionary."""
        return self.current_metrics.daily_pnl
        
    async def initialize(self, starting_balance: Optional[Decimal] = None):
        """Initialize P&L tracker with starting balance."""
        if starting_balance:
            self.account_balance = starting_balance
            self.peak_balance = starting_balance
        
        # Add initial equity curve point
        self.equity_curve.append((self._time_provider.now(), self.account_balance))
        
        logger.info(f"P&L Tracker initialized with balance: {self.account_balance}")
    
    async def record_trade_open(self, trade_data: Dict[str, Any]) -> None:
        """Record a new trade opening."""
        async with self._lock:
            position_id = trade_data['position_id']
            
            # Store in open positions
            self.open_positions[position_id] = {
                'position_id': position_id,
                'symbol': trade_data['symbol'],
                'side': trade_data['side'],
                'quantity': Decimal(str(trade_data['quantity'])),
                'entry_price': Decimal(str(trade_data['entry_price'])),
                'entry_time': trade_data.get('entry_time', self._time_provider.now()),
                'strategy': trade_data.get('strategy', 'unknown'),
                'stop_loss': Decimal(str(trade_data.get('stop_loss', 0))),
                'take_profit': Decimal(str(trade_data.get('take_profit', 0))),
                'commission': Decimal(str(trade_data.get('commission', 0))),
                'unrealized_pnl': Decimal('0')
            }
            
            # Update commission paid
            self.current_metrics.commission_paid += self.open_positions[position_id]['commission']
            
            # Publish event if publisher available
            if self._event_publisher:
                await self._event_publisher.publish(
                    'pnl.trade_opened',
                    {'position_id': position_id, 'symbol': trade_data['symbol']}
                )
    
    async def update_position_pnl(
        self,
        position_id: str,
        current_price: Decimal,
        partial_exit: Optional[Dict[str, Any]] = None
    ) -> None:
        """Update P&L for an open position."""
        async with self._lock:
            if position_id not in self.open_positions:
                return
            
            position = self.open_positions[position_id]
            
            # Handle partial exit
            if partial_exit:
                exit_quantity = Decimal(str(partial_exit['quantity']))
                exit_price = Decimal(str(partial_exit['price']))
                commission = Decimal(str(partial_exit.get('commission', 0)))
                
                # Calculate realized P&L for partial exit
                if position['side'] == 'BUY':
                    pnl = (exit_price - position['entry_price']) * exit_quantity
                else:
                    pnl = (position['entry_price'] - exit_price) * exit_quantity
                
                # Update position
                position['quantity'] -= exit_quantity
                
                # Record partial close
                await self._record_trade_close(
                    position_id=f"{position_id}_partial_{self._time_provider.now().timestamp()}",
                    position_data=position,
                    exit_price=exit_price,
                    exit_quantity=exit_quantity,
                    commission=commission,
                    pnl=pnl
                )
            
            # Update unrealized P&L for remaining position
            if position['quantity'] > 0:
                if position['side'] == 'BUY':
                    position['unrealized_pnl'] = (current_price - position['entry_price']) * position['quantity']
                else:
                    position['unrealized_pnl'] = (position['entry_price'] - current_price) * position['quantity']
                
                # Update current metrics
                await self._update_unrealized_totals()
    
    async def record_trade_close(
        self,
        position_id: str,
        exit_price: Decimal,
        exit_time: Optional[Any] = None,
        commission: Decimal = Decimal('0')
    ) -> None:
        """Record a trade closing."""
        async with self._lock:
            if position_id not in self.open_positions:
                logger.warning(f"Position {position_id} not found in open positions")
                return
            
            position = self.open_positions[position_id]
            
            # Calculate P&L
            if position['side'] == 'BUY':
                pnl = (exit_price - position['entry_price']) * position['quantity']
            else:
                pnl = (position['entry_price'] - exit_price) * position['quantity']
            
            # Record the close
            await self._record_trade_close(
                position_id=position_id,
                position_data=position,
                exit_price=exit_price,
                exit_quantity=position['quantity'],
                commission=commission,
                pnl=pnl,
                exit_time=exit_time
            )
            
            # Remove from open positions
            del self.open_positions[position_id]
            
            # Update unrealized totals
            await self._update_unrealized_totals()
    
    async def _record_trade_close(
        self,
        position_id: str,
        position_data: Dict[str, Any],
        exit_price: Decimal,
        exit_quantity: Decimal,
        commission: Decimal,
        pnl: Decimal,
        exit_time: Optional[Any] = None
    ):
        """Internal method to record trade close."""
        exit_time = exit_time or self._time_provider.now()
        
        # Create trade record
        # Handle timezone differences
        entry_time = position_data['entry_time']
        
        # Ensure both times are comparable
        if hasattr(entry_time, 'tzinfo') and hasattr(exit_time, 'tzinfo'):
            # Both have timezone info, check if one is None
            if entry_time.tzinfo is None and exit_time.tzinfo is not None:
                # Make entry_time aware
                from datetime import timezone
                entry_time = entry_time.replace(tzinfo=timezone.utc)
            elif entry_time.tzinfo is not None and exit_time.tzinfo is None:
                # Make exit_time aware
                from datetime import timezone
                exit_time = exit_time.replace(tzinfo=timezone.utc)
        
        trade_record = {
            'position_id': position_id,
            'symbol': position_data['symbol'],
            'side': position_data['side'],
            'quantity': float(exit_quantity),
            'entry_price': float(position_data['entry_price']),
            'exit_price': float(exit_price),
            'entry_time': entry_time,
            'exit_time': exit_time,
            'duration': (exit_time - entry_time).total_seconds() / 60 if entry_time and exit_time else 0,  # minutes
            'gross_pnl': float(pnl),
            'commission': float(commission),
            'net_pnl': float(pnl - commission),
            'strategy': position_data['strategy'],
            'outcome': self._classify_outcome(pnl - commission)
        }
        
        # Add to history
        self.trades_history.append(trade_record)
        
        # Update metrics
        await self._update_metrics_for_trade(trade_record)
        
        # Update equity curve
        self.account_balance += pnl - commission
        self.equity_curve.append((exit_time, self.account_balance))
        
        # Check for new peak
        if self.account_balance > self.peak_balance:
            self.peak_balance = self.account_balance
        
        # Update drawdown
        await self._update_drawdown()
        
        # Publish event if publisher available
        if self._event_publisher:
            await self._event_publisher.publish(
                'pnl.trade_closed',
                trade_record
            )
        
        # Record metrics if collector available
        if self._metrics_collector:
            self._metrics_collector.record_trade_outcome(
                trade_record['symbol'],
                Decimal(str(trade_record['net_pnl'])),
                int(trade_record['duration']),
                trade_record['outcome']
            )
    
    async def _update_metrics_for_trade(self, trade_record: Dict[str, Any]):
        """Update all metrics for a completed trade."""
        gross_pnl = Decimal(str(trade_record['gross_pnl']))
        net_pnl = Decimal(str(trade_record['net_pnl']))
        symbol = trade_record['symbol']
        strategy = trade_record['strategy']
        outcome = trade_record['outcome']
        trade_date = trade_record['exit_time'].date()
        trade_hour = trade_record['exit_time'].hour
        
        # Update current metrics
        # Based on tests, realized_pnl should be net P&L (gross - commission)
        self.current_metrics.realized_pnl += net_pnl
        self.current_metrics.commission_paid += Decimal(str(trade_record['commission']))
        self.current_metrics.total_trades += 1
        
        # Update by outcome
        if outcome == TradeOutcome.WIN:
            self.current_metrics.winning_trades += 1
            # Based on tests, gross_profit should be gross PnL minus commission
            self.current_metrics.gross_profit += net_pnl
            self.current_metrics.consecutive_wins += 1
            self.current_metrics.consecutive_losses = 0
            
            if gross_pnl > self.current_metrics.largest_win:
                self.current_metrics.largest_win = gross_pnl
            
            if self.current_metrics.consecutive_wins > self.current_metrics.max_consecutive_wins:
                self.current_metrics.max_consecutive_wins = self.current_metrics.consecutive_wins
                
        elif outcome == TradeOutcome.LOSS:
            self.current_metrics.losing_trades += 1
            # Based on tests, gross_loss should be absolute net PnL
            self.current_metrics.gross_loss += abs(net_pnl)
            self.current_metrics.consecutive_losses += 1
            self.current_metrics.consecutive_wins = 0
            
            if abs(gross_pnl) > abs(self.current_metrics.largest_loss):
                self.current_metrics.largest_loss = gross_pnl
            
            if self.current_metrics.consecutive_losses > self.current_metrics.max_consecutive_losses:
                self.current_metrics.max_consecutive_losses = self.current_metrics.consecutive_losses
                
        else:  # Breakeven
            self.current_metrics.breakeven_trades += 1
            self.current_metrics.consecutive_wins = 0
            self.current_metrics.consecutive_losses = 0
        
        # Update symbol and strategy metrics
        self.current_metrics.trades_by_symbol[symbol] += 1
        self.current_metrics.pnl_by_symbol[symbol] += net_pnl
        self.current_metrics.pnl_by_strategy[strategy] += net_pnl
        self.current_metrics.daily_pnl[trade_date] += net_pnl
        self.current_metrics.hourly_pnl[trade_hour] += net_pnl
        
        # Update calculated metrics
        await self._update_calculated_metrics()
        
        # Update period metrics
        await self._update_period_metrics(trade_record)
    
    async def _update_calculated_metrics(self):
        """Update calculated metrics like win rate, profit factor, etc."""
        metrics = self.current_metrics
        
        # Win rate
        if metrics.total_trades > 0:
            metrics.win_rate = metrics.winning_trades / metrics.total_trades
        
        # Average win/loss
        if metrics.winning_trades > 0:
            metrics.average_win = metrics.gross_profit / metrics.winning_trades
        
        if metrics.losing_trades > 0:
            metrics.average_loss = metrics.gross_loss / metrics.losing_trades
        
        # Profit factor
        if metrics.gross_loss > 0:
            metrics.profit_factor = float(metrics.gross_profit / metrics.gross_loss)
        
        # Expectancy
        if metrics.total_trades > 0:
            win_expectancy = Decimal(str(metrics.win_rate)) * metrics.average_win
            loss_expectancy = Decimal(str(1 - metrics.win_rate)) * metrics.average_loss
            metrics.expectancy = win_expectancy - loss_expectancy
        
        # ROI
        if self.account_balance > 0:
            initial_balance = self.equity_curve[0][1] if self.equity_curve else self.account_balance
            metrics.roi = float((self.account_balance - initial_balance) / initial_balance)
        
        # Sharpe ratio (simplified)
        await self._calculate_sharpe_ratio()
        
        # Sortino ratio (simplified)
        await self._calculate_sortino_ratio()
    
    async def _calculate_sharpe_ratio(self):
        """Calculate Sharpe ratio from returns."""
        if len(self.trades_history) < 2:
            return
        
        # Calculate returns
        returns = []
        for i in range(1, len(self.equity_curve)):
            prev_balance = self.equity_curve[i-1][1]
            curr_balance = self.equity_curve[i][1]
            if prev_balance > 0:
                ret = float((curr_balance - prev_balance) / prev_balance)
                returns.append(ret)
        
        if not returns:
            return
        
        # Calculate Sharpe (assuming 0 risk-free rate)
        avg_return = sum(returns) / len(returns)
        
        if len(returns) > 1:
            variance = sum((r - avg_return) ** 2 for r in returns) / (len(returns) - 1)
            std_dev = variance ** 0.5
            
            if std_dev > 0:
                # Annualized Sharpe (assuming 252 trading days)
                sharpe = (avg_return / std_dev) * (252 ** 0.5)
                self.current_metrics.sharpe_ratio = sharpe
                return sharpe
        
        return 0.0
    
    async def _calculate_sortino_ratio(self):
        """Calculate Sortino ratio (downside deviation)."""
        if len(self.trades_history) < 2:
            return
        
        # Calculate returns
        returns = []
        for i in range(1, len(self.equity_curve)):
            prev_balance = self.equity_curve[i-1][1]
            curr_balance = self.equity_curve[i][1]
            if prev_balance > 0:
                ret = float((curr_balance - prev_balance) / prev_balance)
                returns.append(ret)
        
        if not returns:
            return
        
        # Calculate downside deviation
        avg_return = sum(returns) / len(returns)
        negative_returns = [r for r in returns if r < 0]
        
        if negative_returns:
            downside_variance = sum(r ** 2 for r in negative_returns) / len(negative_returns)
            downside_dev = downside_variance ** 0.5
            
            if downside_dev > 0:
                # Annualized Sortino
                self.current_metrics.sortino_ratio = (avg_return / downside_dev) * (252 ** 0.5)
    
    async def _update_unrealized_totals(self):
        """Update total unrealized P&L."""
        total_unrealized = Decimal('0')
        
        for position in self.open_positions.values():
            total_unrealized += position['unrealized_pnl']
        
        self.current_metrics.unrealized_pnl = total_unrealized
    
    async def _update_drawdown(self):
        """Update drawdown metrics."""
        if self.peak_balance > 0:
            drawdown = (self.peak_balance - self.account_balance) / self.peak_balance
            self.current_metrics.current_drawdown = drawdown
            
            if drawdown > self.current_metrics.max_drawdown:
                self.current_metrics.max_drawdown = drawdown
            
            # Track drawdown periods
            if drawdown > 0:
                if not self.drawdown_periods or self.drawdown_periods[-1].get('end_time'):
                    # Start new drawdown period
                    self.drawdown_periods.append({
                        'start_time': self._time_provider.now(),
                        'start_balance': self.peak_balance,
                        'peak_drawdown': drawdown
                    })
                else:
                    # Update current drawdown period
                    current_period = self.drawdown_periods[-1]
                    if drawdown > current_period['peak_drawdown']:
                        current_period['peak_drawdown'] = drawdown
            else:
                # End drawdown period
                if self.drawdown_periods and not self.drawdown_periods[-1].get('end_time'):
                    self.drawdown_periods[-1]['end_time'] = self._time_provider.now()
                    duration = self.drawdown_periods[-1]['end_time'] - self.drawdown_periods[-1]['start_time']
                    
                    if duration > self.current_metrics.max_drawdown_duration:
                        self.current_metrics.max_drawdown_duration = duration
    
    async def _update_period_metrics(self, trade_record: Dict[str, Any]):
        """Update period-specific metrics."""
        trade_time = trade_record['exit_time']
        
        # Update daily metrics
        trade_date = trade_time.date()
        if trade_date not in self.daily_metrics:
            self.daily_metrics[trade_date] = PnLMetrics()
        
        # This would duplicate all the metric updates for the daily period
        # Simplified for brevity
        
        # Update other periods (weekly, monthly, etc.)
        # Also simplified for brevity
    
    def _classify_outcome(self, net_pnl: Decimal) -> TradeOutcome:
        """Classify trade outcome."""
        if net_pnl > Decimal('0.01'):  # Small threshold for breakeven
            return TradeOutcome.WIN
        elif net_pnl < Decimal('-0.01'):
            return TradeOutcome.LOSS
        else:
            return TradeOutcome.BREAKEVEN
    
    async def get_performance_summary(
        self,
        start_date: Optional[Any] = None,
        end_date: Optional[Any] = None
    ) -> Dict[str, Any]:
        """Get comprehensive performance summary."""
        # Filter trades by date if specified
        if start_date or end_date:
            filtered_trades = []
            for trade in self.trades_history:
                trade_time = trade['exit_time']
                if start_date and trade_time < start_date:
                    continue
                if end_date and trade_time > end_date:
                    continue
                filtered_trades.append(trade)
            
            # Calculate metrics for filtered period
            # (Implementation would recalculate all metrics for the period)
        
        # Get appropriate metrics
        metrics = self.current_metrics
        
        summary = metrics.to_dict()
        
        # Add additional summary info
        summary['account_balance'] = float(self.account_balance)
        summary['peak_balance'] = float(self.peak_balance)
        summary['open_positions'] = len(self.open_positions)
        summary['total_positions_value'] = float(
            sum(p['quantity'] * p['entry_price'] for p in self.open_positions.values())
        )
        
        # Add best/worst performing symbols
        if metrics.pnl_by_symbol:
            sorted_symbols = sorted(
                metrics.pnl_by_symbol.items(),
                key=lambda x: x[1],
                reverse=True
            )
            summary['best_symbol'] = sorted_symbols[0] if sorted_symbols else None
            summary['worst_symbol'] = sorted_symbols[-1] if sorted_symbols else None
        
        # Add best/worst performing strategies
        if metrics.pnl_by_strategy:
            sorted_strategies = sorted(
                metrics.pnl_by_strategy.items(),
                key=lambda x: x[1],
                reverse=True
            )
            summary['best_strategy'] = sorted_strategies[0] if sorted_strategies else None
            summary['worst_strategy'] = sorted_strategies[-1] if sorted_strategies else None
        
        # Add time-based analysis
        if metrics.hourly_pnl:
            best_hour = max(metrics.hourly_pnl.items(), key=lambda x: x[1])
            worst_hour = min(metrics.hourly_pnl.items(), key=lambda x: x[1])
            summary['best_trading_hour'] = best_hour
            summary['worst_trading_hour'] = worst_hour
        
        return summary
    
    async def get_equity_curve(
        self,
        start_date: Optional[Any] = None,
        end_date: Optional[Any] = None
    ) -> List[Dict[str, Any]]:
        """Get equity curve data."""
        curve_data = []
        
        for timestamp, balance in self.equity_curve:
            if start_date and timestamp < start_date:
                continue
            if end_date and timestamp > end_date:
                continue
            
            curve_data.append({
                'timestamp': timestamp.isoformat() if hasattr(timestamp, 'isoformat') else str(timestamp),
                'balance': float(balance),
                'drawdown': float(
                    (self.peak_balance - balance) / self.peak_balance
                    if self.peak_balance > 0 else 0
                )
            })
        
        return curve_data
    
    async def export_trades_history(
        self,
        format: str = 'json',
        filepath: Optional[str] = None
    ) -> Optional[str]:
        """Export trades history to file."""
        if format == 'json':
            # Convert datetime objects to strings
            export_data = []
            for trade in self.trades_history:
                trade_copy = trade.copy()
                trade_copy['entry_time'] = trade_copy['entry_time'].isoformat() if hasattr(trade_copy['entry_time'], 'isoformat') else str(trade_copy['entry_time'])
                trade_copy['exit_time'] = trade_copy['exit_time'].isoformat() if hasattr(trade_copy['exit_time'], 'isoformat') else str(trade_copy['exit_time'])
                export_data.append(trade_copy)
            
            if filepath:
                with open(filepath, 'w') as f:
                    json.dump(export_data, f, indent=2)
                return filepath
            else:
                return json.dumps(export_data, indent=2)
        
        # Add CSV export if needed
        
        return None
    
    async def add_trade(self, trade_data: Dict[str, Any]) -> None:
        """Add a completed trade to the tracker."""
        async with self._lock:
            # Create trade record with proper formatting
            trade_record = {
                'trade_id': trade_data.get('trade_id', f"trade_{self._time_provider.now().timestamp()}"),
                'position_id': trade_data.get('position_id', f"pos_{self._time_provider.now().timestamp()}"),
                'symbol': trade_data['symbol'],
                'side': trade_data['side'],
                'quantity': float(trade_data.get('quantity', 0)),
                'entry_price': float(trade_data.get('entry_price', 0)),
                'exit_price': float(trade_data.get('exit_price', 0)),
                'entry_time': trade_data.get('entry_time', self._time_provider.now()),
                'exit_time': trade_data.get('closed_at', self._time_provider.now()),
                'duration': 0,  # Will be calculated
                'gross_pnl': float(trade_data.get('pnl', trade_data.get('realized_pnl', 0))),
                'commission': float(trade_data.get('commission', 0)),
                'net_pnl': float(trade_data.get('pnl', trade_data.get('realized_pnl', 0))) - float(trade_data.get('commission', 0)),
                'strategy': trade_data.get('strategy', 'unknown'),
                'outcome': self._classify_outcome(Decimal(str(trade_data.get('pnl', trade_data.get('realized_pnl', 0)))) - Decimal(str(trade_data.get('commission', 0))))
            }
            
            # Calculate duration with timezone handling
            entry_time = trade_record['entry_time']
            exit_time = trade_record['exit_time']
            
            # Ensure both times are comparable
            if hasattr(entry_time, 'tzinfo') and hasattr(exit_time, 'tzinfo'):
                # Both have timezone info, check if one is None
                if entry_time.tzinfo is None and exit_time.tzinfo is not None:
                    # Make entry_time aware
                    from datetime import timezone
                    entry_time = entry_time.replace(tzinfo=timezone.utc)
                elif entry_time.tzinfo is not None and exit_time.tzinfo is None:
                    # Make exit_time aware
                    from datetime import timezone
                    exit_time = exit_time.replace(tzinfo=timezone.utc)
            
            if hasattr(exit_time, 'timestamp') and hasattr(entry_time, 'timestamp'):
                trade_record['duration'] = (exit_time - entry_time).total_seconds() / 60
            
            # Add to history
            self.trades_history.append(trade_record)
            
            # Update metrics
            await self._update_metrics_for_trade(trade_record)
            
            # Update account balance
            self.account_balance += Decimal(str(trade_record['net_pnl']))
            self.equity_curve.append((trade_record['exit_time'], self.account_balance))
            
            # Check for new peak
            if self.account_balance > self.peak_balance:
                self.peak_balance = self.account_balance
            
            # Update drawdown
            await self._update_drawdown()
    
    async def update_position(self, position_data: Dict[str, Any]) -> None:
        """Update an open position's current state."""
        async with self._lock:
            position_id = position_data['position_id']
            
            # Convert to internal format
            position = {
                'position_id': position_id,
                'symbol': position_data['symbol'],
                'side': position_data['side'],
                'quantity': Decimal(str(position_data.get('quantity', 0))),
                'entry_price': Decimal(str(position_data.get('avg_entry_price', position_data.get('entry_price', 0)))),
                'entry_time': position_data.get('entry_time', self._time_provider.now()),
                'strategy': position_data.get('strategy', 'unknown'),
                'stop_loss': Decimal(str(position_data.get('stop_loss', 0))),
                'take_profit': Decimal(str(position_data.get('take_profit', 0))),
                'commission': Decimal(str(position_data.get('commission', 0))),
                'unrealized_pnl': Decimal(str(position_data.get('unrealized_pnl', 0))),
                'current_price': Decimal(str(position_data.get('current_price', 0)))
            }
            
            # Store/update position
            self.open_positions[position_id] = position
            
            # Update unrealized totals
            await self._update_unrealized_totals()
    
    async def get_snapshot(self) -> PnLSnapshot:
        """Get current P&L snapshot."""
        async with self._lock:
            snapshot_data = {
                'timestamp': self._time_provider.now(),
                'realized_pnl': float(self.current_metrics.realized_pnl),
                'unrealized_pnl': float(self.current_metrics.unrealized_pnl),
                'total_pnl': float(self.current_metrics.realized_pnl + self.current_metrics.unrealized_pnl),
                'commission': float(self.current_metrics.commission_paid),
                'net_pnl': float(self.current_metrics.realized_pnl + self.current_metrics.unrealized_pnl),
                'position_count': len(self.open_positions),
                'trade_count': self.current_metrics.total_trades,
                'win_count': self.current_metrics.winning_trades,
                'loss_count': self.current_metrics.losing_trades,
                'win_rate': self.current_metrics.win_rate,
                'avg_win': float(self.current_metrics.average_win),
                'avg_loss': float(self.current_metrics.average_loss),
                'profit_factor': self.current_metrics.profit_factor,
                'sharpe_ratio': self.current_metrics.sharpe_ratio,
                'max_drawdown': float(self.current_metrics.max_drawdown),
                'account_balance': float(self.account_balance)
            }
            
            return PnLSnapshot(snapshot_data)
    
    async def get_period_pnl(self, period: PnLPeriod) -> Union[Decimal, List[Dict[str, Any]]]:
        """Get P&L for a specific period."""
        if period == PnLPeriod.DAILY:
            # Return list of daily P&L records
            daily_records = []
            for date, pnl in self.current_metrics.daily_pnl.items():
                if pnl != Decimal('0'):  # Only include days with activity
                    daily_records.append({
                        'date': date,
                        'net_pnl': float(pnl),
                        'gross_pnl': float(pnl),  # Simplified - same as net
                        'commission': 0  # Would need to track commission by day
                    })
            return daily_records
        elif period == PnLPeriod.ALL_TIME:
            return self.current_metrics.realized_pnl
        else:
            # For other periods, calculate from trades history
            # This is simplified - full implementation would track period metrics
            return self.current_metrics.realized_pnl
    
    async def get_symbol_pnl(self, symbol: Optional[str] = None) -> Union[Decimal, Dict[str, Dict[str, Any]]]:
        """Get P&L for a specific symbol or all symbols."""
        if symbol:
            return self.current_metrics.pnl_by_symbol.get(symbol, Decimal('0'))
        else:
            # Return P&L data for all symbols
            result = {}
            for sym in self.current_metrics.pnl_by_symbol:
                # Count trades and commission for this symbol
                trade_count = 0
                commission = Decimal('0')
                for trade in self.trades_history:
                    if trade['symbol'] == sym:
                        trade_count += 1
                        commission += Decimal(str(trade['commission']))
                
                result[sym] = {
                    'realized_pnl': self.current_metrics.pnl_by_symbol[sym],
                    'commission': commission,
                    'trade_count': trade_count
                }
            return result
    
    async def calculate_drawdown(self) -> Dict[str, Any]:
        """Calculate current and max drawdown."""
        current_drawdown = self.peak_balance - self.account_balance
        
        # Update max drawdown if current is greater
        if current_drawdown > self.current_metrics.max_drawdown:
            self.current_metrics.max_drawdown = current_drawdown
        
        max_drawdown = self.current_metrics.max_drawdown
        
        # Calculate percentages
        current_drawdown_pct = current_drawdown / self.peak_balance if self.peak_balance > 0 else Decimal('0')
        max_drawdown_pct = max_drawdown / self.peak_balance if self.peak_balance > 0 else Decimal('0')
        
        return {
            'current_drawdown': current_drawdown,
            'current_drawdown_pct': current_drawdown_pct,
            'max_drawdown': max_drawdown,
            'max_drawdown_pct': max_drawdown_pct,
            'max_drawdown_duration': self.current_metrics.max_drawdown_duration,
            'peak_balance': self.peak_balance,
            'current_balance': self.account_balance
        }
    
    async def reset_daily_pnl(self) -> None:
        """Reset daily P&L at day boundary."""
        async with self._lock:
            # Move today's metrics to history
            today = self._time_provider.today().date()
            if today in self.current_metrics.daily_pnl:
                # Store in daily metrics history
                if today not in self.daily_metrics:
                    self.daily_metrics[today] = PnLMetrics()
                # Reset today's P&L to 0
                self.current_metrics.daily_pnl[today] = Decimal('0')
            
            logger.info(f"Daily P&L reset completed for {today}")
    
    async def export_history(self, format: str = 'json') -> Dict[str, Any]:
        """Export comprehensive trading history."""
        return {
            'trades': self.trades_history,
            'snapshots': [],  # No snapshot history stored
            'daily_pnl': {str(k): float(v) for k, v in self.current_metrics.daily_pnl.items()},
            'metrics': {
                'total_trades': self.current_metrics.total_trades,
                'winning_trades': self.current_metrics.winning_trades,
                'losing_trades': self.current_metrics.losing_trades,
                'realized_pnl': float(self.current_metrics.realized_pnl),
                'commission_paid': float(self.current_metrics.commission_paid)
            }
        }
    
    async def calculate_metrics(self) -> PnLMetrics:
        """Calculate and return current metrics."""
        await self._update_calculated_metrics()
        return self.current_metrics
    
    @property
    def current_consecutive_wins(self) -> int:
        """Current consecutive wins."""
        return self.current_metrics.consecutive_wins
    
    @property
    def max_consecutive_wins(self) -> int:
        """Maximum consecutive wins."""
        return self.current_metrics.max_consecutive_wins
    
    @property
    def current_consecutive_losses(self) -> int:
        """Current consecutive losses."""
        return self.current_metrics.consecutive_losses