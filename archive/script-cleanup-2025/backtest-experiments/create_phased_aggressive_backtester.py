#!/usr/bin/env python
"""Phased aggressive backtester implementing the strategy from FINAL_AGGRESSIVE_STRATEGY.md."""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import os
from scripts.create_enhanced_backtester import Enhanced4HBacktester

class PhasedAggressiveBacktester(Enhanced4HBacktester):
    """Implements phased approach to aggressive trading for sustainable high returns."""
    
    def __init__(self, symbols: list, initial_capital: float = 100000):
        super().__init__(symbols, initial_capital)
        
        # Track performance for phase adjustments
        self.weekly_returns = []
        self.monthly_returns = []
        self.current_phase = 1
        self.phase_start_date = None
        self.phase_performance = {'phase': 1, 'trades': 0, 'return': 0}
        
        # Phase 1 Settings (Conservative Start)
        self.set_phase_parameters(1)
        
        # Circuit breakers
        self.daily_loss_limit = -0.05    # -5% daily
        self.weekly_loss_limit = -0.10   # -10% weekly
        self.monthly_loss_limit = -0.15  # -15% monthly
        self.max_drawdown_limit = -0.20  # -20% max drawdown
        
        # Performance tracking
        self.daily_pnl = {}
        self.weekly_pnl = {}
        self.circuit_breaker_active = False
        self.position_size_multiplier = 1.0
        
        print("\nPhased Aggressive Backtester initialized")
        print(f"Starting in Phase {self.current_phase}")
        print("Circuit breakers active:")
        print(f"  Daily: {self.daily_loss_limit:.1%}")
        print(f"  Weekly: {self.weekly_loss_limit:.1%}")
        print(f"  Monthly: {self.monthly_loss_limit:.1%}")
    
    def set_phase_parameters(self, phase: int):
        """Set parameters based on current phase."""
        if phase == 1:
            # Phase 1: Conservative start
            self.base_position_pct = 0.15    # 15% base
            self.max_position_pct = 0.25     # 25% max
            self.max_positions = 3
            self.risk_per_trade = 0.02       # 2% risk
            self.signal_quality_threshold = 0.7
        
        elif phase == 2:
            # Phase 2: Scale up
            self.base_position_pct = 0.25    # 25% base
            self.max_position_pct = 0.35     # 35% max
            self.max_positions = 4
            self.risk_per_trade = 0.025      # 2.5% risk
            self.signal_quality_threshold = 0.65
        
        elif phase == 3:
            # Phase 3: Full aggressive
            self.base_position_pct = 0.35    # 35% base
            self.max_position_pct = 0.50     # 50% max
            self.max_positions = 5
            self.risk_per_trade = 0.03       # 3% risk
            self.signal_quality_threshold = 0.6
        
        print(f"\nPhase {phase} parameters set:")
        print(f"  Position size: {self.base_position_pct:.0%}-{self.max_position_pct:.0%}")
        print(f"  Max positions: {self.max_positions}")
        print(f"  Risk per trade: {self.risk_per_trade:.1%}")
    
    def calculate_smart_position_size(self, account_balance: float, 
                                    signal_quality: float,
                                    current_volatility: float,
                                    recent_performance: float) -> float:
        """Calculate position size based on FINAL_AGGRESSIVE_STRATEGY formula."""
        
        # Base position size (phase-dependent)
        base_size = account_balance * self.base_position_pct
        
        # Quality multiplier (0.8x to 1.5x)
        if signal_quality > 0.8:
            quality_mult = 1.5
        elif signal_quality > 0.7:
            quality_mult = 1.2
        elif signal_quality > 0.6:
            quality_mult = 1.0
        else:
            quality_mult = 0.8
        
        # Volatility adjustment
        normal_volatility = 0.001  # 10 pips/hour
        vol_ratio = normal_volatility / max(current_volatility, 0.0005)
        vol_mult = np.clip(vol_ratio, 0.7, 1.3)
        
        # Performance adjustment
        if recent_performance > 0.05:  # Up 5%+
            perf_mult = 1.2
        elif recent_performance < -0.03:  # Down 3%+
            perf_mult = 0.7
        else:
            perf_mult = 1.0
        
        # Circuit breaker multiplier
        if self.circuit_breaker_active:
            perf_mult *= 0.5
        
        # Calculate final position
        position_size = base_size * quality_mult * vol_mult * perf_mult * self.position_size_multiplier
        
        # Risk check (max risk per trade based on phase)
        stop_loss_pct = 0.002  # 20 pips
        risk_amount = position_size * stop_loss_pct
        max_risk = account_balance * self.risk_per_trade
        
        if risk_amount > max_risk:
            position_size = max_risk / stop_loss_pct
        
        # Leverage check (max 10x)
        if position_size > account_balance * 10:
            position_size = account_balance * 10
        
        # Phase-based max position check
        if position_size > account_balance * self.max_position_pct:
            position_size = account_balance * self.max_position_pct
        
        return position_size
    
    def calculate_position_size_enhanced(self, symbol: str, signal_quality: float, 
                                       current_price: float, atr: float, 
                                       current_volatility: float) -> dict:
        """Enhanced position sizing using smart calculation."""
        
        # Calculate recent performance
        recent_performance = self.calculate_recent_performance()
        
        # Get smart position size
        position_value = self.calculate_smart_position_size(
            self.current_capital,
            signal_quality,
            current_volatility,
            recent_performance
        )
        
        # Minimum position check
        if position_value < 10000:  # $10k minimum
            return {'units': 0, 'notional_value': 0, 'margin_required': 0}
        
        # Calculate stops and targets
        stop_loss_pct = 0.002    # 20 pips
        take_profit_pct = 0.004  # 40 pips (2:1 RR)
        
        # Calculate margin
        margin_required = position_value / self.account_leverage
        
        # Risk calculation
        risk_amount = position_value * stop_loss_pct
        
        return {
            'units': position_value / current_price,
            'notional_value': position_value,
            'margin_required': margin_required,
            'stop_loss_pct': stop_loss_pct,
            'take_profit_pct': take_profit_pct,
            'position_pct': position_value / self.current_capital,
            'risk_amount': risk_amount,
            'phase': self.current_phase
        }
    
    def calculate_recent_performance(self) -> float:
        """Calculate recent performance for position sizing."""
        if len(self.equity_curve) < 5:
            return 0
        
        # Get last week's performance
        recent_equity = self.equity_curve[-5:]
        if len(recent_equity) >= 2:
            return (recent_equity[-1] - recent_equity[0]) / recent_equity[0]
        return 0
    
    def check_circuit_breakers(self, current_time: pd.Timestamp):
        """Check and activate circuit breakers if needed."""
        current_date = current_time.date()
        
        # Daily loss check
        if current_date in self.daily_pnl:
            daily_return = self.daily_pnl[current_date] / self.initial_capital
            if daily_return <= self.daily_loss_limit:
                self.circuit_breaker_active = True
                return True, "daily_loss_limit"
        
        # Weekly loss check
        week_key = f"{current_time.year}-W{current_time.week}"
        if week_key in self.weekly_pnl:
            weekly_return = self.weekly_pnl[week_key] / self.initial_capital
            if weekly_return <= self.weekly_loss_limit:
                self.position_size_multiplier = 0.5
                return True, "weekly_loss_limit"
        
        # Monthly loss check
        month_key = f"{current_time.year}-{current_time.month}"
        monthly_pnl = sum(pnl for date, pnl in self.daily_pnl.items() 
                         if date.year == current_time.year and date.month == current_time.month)
        if monthly_pnl / self.initial_capital <= self.monthly_loss_limit:
            # Revert to Phase 1
            self.current_phase = 1
            self.set_phase_parameters(1)
            return True, "monthly_loss_limit"
        
        # Drawdown check
        if len(self.equity_curve) > 0:
            peak = max(self.equity_curve)
            current_dd = (self.current_capital - peak) / peak
            if current_dd <= self.max_drawdown_limit:
                return True, "max_drawdown_limit"
        
        return False, None
    
    def update_phase_based_on_performance(self, current_time: pd.Timestamp):
        """Update trading phase based on performance."""
        # Only update phase monthly
        if self.phase_start_date is None:
            self.phase_start_date = current_time
            return
        
        months_in_phase = (current_time - self.phase_start_date).days / 30
        
        if months_in_phase >= 1:
            # Calculate phase performance
            phase_return = (self.current_capital - self.initial_capital) / self.initial_capital
            monthly_return = phase_return / max(months_in_phase, 1)
            
            # Phase progression logic
            if self.current_phase == 1 and monthly_return >= 0.03:  # 3%+ monthly
                self.current_phase = 2
                self.set_phase_parameters(2)
                self.phase_start_date = current_time
                print(f"\n🎯 Advancing to Phase 2 (Monthly return: {monthly_return:.1%})")
            
            elif self.current_phase == 2 and monthly_return >= 0.05:  # 5%+ monthly
                self.current_phase = 3
                self.set_phase_parameters(3)
                self.phase_start_date = current_time
                print(f"\n🚀 Advancing to Phase 3 (Monthly return: {monthly_return:.1%})")
    
    def should_exit_position_enhanced(self, position: dict, current_bar: pd.Series,
                                    current_price: float, current_time: pd.Timestamp,
                                    atr: float) -> tuple:
        """Enhanced exit management from FINAL_AGGRESSIVE_STRATEGY."""
        
        # Calculate P&L
        if position['type'] == 'long':
            pnl_pct = (current_price - position['entry_price']) / position['entry_price']
        else:
            pnl_pct = (position['entry_price'] - current_price) / position['entry_price']
        
        pnl_pips = pnl_pct * 10000  # Convert to pips
        
        # Quick profits: Take 50% off at 20 pips
        if pnl_pips >= 20 and not position.get('partial_taken'):
            position['partial_taken'] = True
            position['units'] *= 0.5  # Take half off
            return True, 'quick_profit_20pips'
        
        # Move to breakeven at 15 pips
        if pnl_pips >= 15 and not position.get('breakeven'):
            position['breakeven'] = True
            position['stop_loss_pct'] = 0
        
        # Trailing stop after 30 pips
        if pnl_pips >= 30:
            trailing_stop = 0.002  # 20 pip trailing
            if position['type'] == 'long':
                new_stop = current_price - (current_price * trailing_stop)
                if 'trailing_stop_price' not in position:
                    position['trailing_stop_price'] = new_stop
                else:
                    position['trailing_stop_price'] = max(position['trailing_stop_price'], new_stop)
                
                if current_price <= position['trailing_stop_price']:
                    return True, 'trailing_stop'
            else:
                new_stop = current_price + (current_price * trailing_stop)
                if 'trailing_stop_price' not in position:
                    position['trailing_stop_price'] = new_stop
                else:
                    position['trailing_stop_price'] = min(position['trailing_stop_price'], new_stop)
                
                if current_price >= position['trailing_stop_price']:
                    return True, 'trailing_stop'
        
        # Time stop: Exit after 24 hours if < 10 pips
        hours_held = (current_time - position['entry_time']).total_seconds() / 3600
        if hours_held > 24 and pnl_pips < 10:
            return True, 'time_stop_24h'
        
        # Standard stops
        if pnl_pct <= -position['stop_loss_pct']:
            return True, 'stop_loss'
        
        if pnl_pct >= position['take_profit_pct']:
            return True, 'take_profit'
        
        return False, None
    
    def _open_position(self, symbol: str, signal: dict, price: float, 
                      timestamp: pd.Timestamp, volatility: float):
        """Open a new position with phase tracking."""
        # Call parent method
        super()._open_position(symbol, signal, price, timestamp, volatility)
        
        # Add phase information if position was opened
        if symbol in self.positions:
            self.positions[symbol]['phase'] = self.current_phase
    
    def _update_performance_tracking(self, timestamp: pd.Timestamp):
        """Update performance tracking for circuit breakers."""
        current_date = timestamp.date()
        
        # Daily P&L
        if current_date not in self.daily_pnl:
            self.daily_pnl[current_date] = 0
        
        # Update daily P&L
        current_pnl = self.current_capital - self.initial_capital
        if len(self.daily_pnl) > 0:
            prev_dates = sorted([d for d in self.daily_pnl.keys() if d < current_date])
            if prev_dates:
                prev_pnl = sum(self.daily_pnl[d] for d in prev_dates)
                self.daily_pnl[current_date] = current_pnl - prev_pnl
        else:
            self.daily_pnl[current_date] = current_pnl
        
        # Weekly P&L
        week_key = f"{timestamp.year}-W{timestamp.week}"
        if week_key not in self.weekly_pnl:
            self.weekly_pnl[week_key] = 0
        
        # Sum this week's daily P&Ls
        week_start = timestamp - timedelta(days=timestamp.weekday())
        week_pnl = sum(pnl for date, pnl in self.daily_pnl.items() 
                      if week_start.date() <= date <= timestamp.date())
        self.weekly_pnl[week_key] = week_pnl
    
    def run_backtest(self, start_date: str, end_date: str):
        """Run phased aggressive backtest with circuit breakers."""
        print("\n" + "="*80)
        print("PHASED AGGRESSIVE FOREX BACKTEST")
        print("="*80)
        print(f"Period: {start_date} to {end_date}")
        print(f"Initial Capital: ${self.initial_capital:,.2f}")
        print("="*80)
        
        # Load all data
        all_data = {}
        all_prices = {}
        
        for symbol in self.symbols:
            df_features = self.load_4h_data(symbol)
            df_prices = self.load_4h_price_data(symbol, start_date, end_date)
            
            if df_features is not None and df_prices is not None:
                df_features = df_features[(df_features.index >= start_date) & 
                                        (df_features.index <= end_date)]
                
                common_index = df_features.index.intersection(df_prices.index)
                if len(common_index) > 0:
                    all_data[symbol] = df_features.loc[common_index]
                    all_prices[symbol] = df_prices.loc[common_index]
                    print(f"  ✅ {symbol}: {len(common_index)} 4H bars")
        
        if not all_data:
            print("❌ No data available")
            return
        
        # Process each bar
        all_timestamps = sorted(set().union(*[set(df.index) for df in all_data.values()]))
        print(f"\nProcessing {len(all_timestamps)} 4H bars...")
        
        for i, timestamp in enumerate(all_timestamps):
            
            # Update performance tracking
            self._update_performance_tracking(timestamp)
            
            # Check circuit breakers
            breaker_triggered, breaker_reason = self.check_circuit_breakers(timestamp)
            if breaker_triggered and breaker_reason == "daily_loss_limit":
                # Skip new trades today
                self.circuit_breaker_active = True
                if (i + 1) % 6 == 0:  # Once per day
                    print(f"  ⚠️  Circuit breaker active: {breaker_reason}")
            else:
                # Reset daily circuit breaker
                if timestamp.hour == 0:
                    self.circuit_breaker_active = False
            
            # Update phase based on performance
            if timestamp.day == 1:  # Check monthly
                self.update_phase_based_on_performance(timestamp)
            
            # Check exits first
            for symbol in list(self.positions.keys()):
                if symbol in all_prices and timestamp in all_prices[symbol].index:
                    position = self.positions[symbol]
                    current_price = all_prices[symbol].loc[timestamp, 'close']
                    current_bar = all_data[symbol].loc[timestamp]
                    atr = current_bar.get('atr_10', 0.0001)
                    
                    should_exit, exit_reason = self.should_exit_position_enhanced(
                        position, current_bar, current_price, timestamp, atr
                    )
                    
                    if should_exit:
                        self._close_position(symbol, current_price, timestamp, exit_reason)
            
            # Evaluate new signals (if not in circuit breaker mode)
            if not self.circuit_breaker_active and len(self.positions) < self.max_positions:
                best_signal = None
                best_quality = 0
                
                for symbol in self.symbols:
                    if symbol in all_data and timestamp in all_data[symbol].index:
                        if symbol not in self.positions:
                            current_bar = all_data[symbol].loc[timestamp]
                            signal = self.generate_signal(symbol, current_bar)
                            
                            if signal['signal'] != 0 and signal['quality'] > self.signal_quality_threshold:
                                if signal['quality'] > best_quality:
                                    best_quality = signal['quality']
                                    best_signal = {
                                        'symbol': symbol,
                                        'signal': signal,
                                        'price': all_prices[symbol].loc[timestamp, 'close'],
                                        'volatility': current_bar.get('volatility_12', 0.001),
                                        'atr': current_bar.get('atr_10', 0.0001)
                                    }
                
                # Take the best signal
                if best_signal:
                    position_info = self.calculate_position_size_enhanced(
                        best_signal['symbol'],
                        best_signal['signal']['quality'],
                        best_signal['price'],
                        best_signal['atr'],
                        best_signal['volatility']
                    )
                    
                    if position_info['units'] > 0:
                        # Call parent's _open_position with correct arguments
                        self._open_position(
                            best_signal['symbol'],
                            best_signal['signal'],
                            best_signal['price'],
                            timestamp,
                            best_signal['volatility']
                        )
            
            # Update equity
            self._update_equity(all_data, all_prices, timestamp)
            
            # Progress report
            if (i + 1) % 150 == 0:  # Every ~25 days
                current_pnl = (self.current_capital - self.initial_capital) / self.initial_capital
                print(f"  Day {(i+1)/6:.0f}: "
                      f"P&L: {current_pnl:+.1%}, "
                      f"Phase: {self.current_phase}, "
                      f"Trades: {len(self.trades)}, "
                      f"Open: {len(self.positions)}")
        
        # Close remaining positions
        print("\nClosing remaining positions...")
        for symbol in list(self.positions.keys()):
            if symbol in all_prices:
                last_price = all_prices[symbol].iloc[-1]['close']
                self._close_position(symbol, last_price, all_timestamps[-1], 'end_of_test')
        
        # Calculate final metrics
        self._calculate_performance()
        self._generate_comprehensive_report()
    
    def _generate_comprehensive_report(self):
        """Generate comprehensive report with phase analysis."""
        print("\n" + "="*80)
        print("BACKTEST RESULTS - PHASED AGGRESSIVE STRATEGY")
        print("="*80)
        
        # Overall performance
        print("\nOVERALL PERFORMANCE")
        print("-"*40)
        print(f"Total Return: {self.metrics['total_return']:+.1%}")
        print(f"Annualized Return: {self.metrics['total_return'] * 2:+.1%}")
        print(f"Max Drawdown: {self.metrics['max_drawdown']:.1%}")
        print(f"Sharpe Ratio: {self.metrics.get('sharpe_ratio', 0):.2f}")
        
        # Trading statistics
        print("\nTRADING STATISTICS")
        print("-"*40)
        print(f"Total Trades: {self.metrics['total_trades']}")
        print(f"Win Rate: {self.metrics['win_rate']:.1%}")
        print(f"Avg Win: ${self.metrics.get('avg_win', 0):.2f}")
        print(f"Avg Loss: ${self.metrics.get('avg_loss', 0):.2f}")
        print(f"Profit Factor: {self.metrics.get('profit_factor', 0):.2f}")
        
        # Position sizing analysis
        if self.trades:
            trades_df = pd.DataFrame(self.trades)
            if 'notional_value' in trades_df.columns:
                print("\nPOSITION SIZING ANALYSIS")
                print("-"*40)
                avg_position = trades_df['notional_value'].mean()
                max_position = trades_df['notional_value'].max()
                print(f"Average Position: ${avg_position:,.0f}")
                print(f"Max Position: ${max_position:,.0f}")
                print(f"As % of Capital: {avg_position/self.initial_capital:.1%}")
                print(f"Effective Leverage: {avg_position/self.initial_capital:.1f}x")
            
            # Phase analysis
            if 'phase' in trades_df.columns:
                print("\nPHASE ANALYSIS")
                print("-"*40)
                for phase in sorted(trades_df['phase'].unique()):
                    phase_trades = trades_df[trades_df['phase'] == phase]
                    phase_return = phase_trades['pnl'].sum() / self.initial_capital
                    print(f"Phase {phase}: {len(phase_trades)} trades, "
                          f"Return: {phase_return:+.1%}")
        
        # Exit analysis
        if 'exit_reasons' in self.metrics:
            print("\nEXIT ANALYSIS")
            print("-"*40)
            total_exits = sum(self.metrics['exit_reasons'].values())
            for reason, count in sorted(self.metrics['exit_reasons'].items(), 
                                      key=lambda x: x[1], reverse=True):
                pct = count / total_exits * 100
                print(f"{reason}: {count} ({pct:.1f}%)")
        
        # Circuit breaker analysis
        print("\nCIRCUIT BREAKER ANALYSIS")
        print("-"*40)
        print(f"Daily Loss Limit: {self.daily_loss_limit:.1%}")
        print(f"Times Triggered: {sum(1 for d, p in self.daily_pnl.items() if p/self.initial_capital <= self.daily_loss_limit)}")
        
        # Monthly returns
        print("\nMONTHLY RETURNS")
        print("-"*40)
        monthly_returns = {}
        for date, pnl in sorted(self.daily_pnl.items()):
            month_key = f"{date.year}-{date.month:02d}"
            if month_key not in monthly_returns:
                monthly_returns[month_key] = 0
            monthly_returns[month_key] += pnl
        
        for month, pnl in monthly_returns.items():
            monthly_return = pnl / self.initial_capital
            print(f"{month}: {monthly_return:+.1%}")


def main():
    """Run phased aggressive backtest."""
    
    symbols = ['EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF']
    
    # Test period
    start_date = '2024-07-01'
    end_date = '2024-12-31'
    
    # Run backtest
    backtester = PhasedAggressiveBacktester(symbols, initial_capital=100000)
    backtester.run_backtest(start_date, end_date)
    
    # Save results
    if backtester.trades:
        trades_df = pd.DataFrame(backtester.trades)
        trades_df.to_csv('output/phased_aggressive_trades.csv', index=False)
        
        with open('output/phased_aggressive_metrics.json', 'w') as f:
            json.dump(backtester.metrics, f, indent=2, default=str)
        
        print("\n✅ Results saved to:")
        print("  - output/phased_aggressive_trades.csv")
        print("  - output/phased_aggressive_metrics.json")

if __name__ == "__main__":
    main()