#!/usr/bin/env python
"""Aggressive but sustainable backtester combining high returns with smart risk management."""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import os
from scripts.create_enhanced_backtester import Enhanced4HBacktester

class AggressiveSustainableBacktester(Enhanced4HBacktester):
    """Aggressive trading with circuit breakers and smart risk management."""
    
    def __init__(self, symbols: list, initial_capital: float = 100000):
        super().__init__(symbols, initial_capital)
        
        # Aggressive parameters
        self.base_risk_per_trade = 0.02  # 2% risk (aggressive)
        self.max_portfolio_heat = 0.12   # 12% total risk
        self.kelly_multiplier = 1.5      # 150% of Kelly
        
        # Circuit breakers
        self.daily_loss_limit = 0.05     # Stop at 5% daily loss
        self.weekly_loss_limit = 0.10    # Reduce at 10% weekly loss
        self.max_correlation_exposure = 0.7
        
        # Session multipliers (aggressive during liquid sessions)
        self.session_multipliers = {
            'session_London2': 1.5,    # Most aggressive
            'session_NewYork1': 1.3,   # Aggressive
            'session_London1': 1.0,    # Normal
            'session_NewYork2': 0.8,   # Careful
            'session_Asian1': 0.5,     # Conservative
            'session_Asian2': 0.5      # Conservative
        }
        
        # Symbol-specific configs based on backtest results
        self.symbol_configs = {
            'USDJPY': {'multiplier': 1.5, 'threshold': 0.00004, 'max_positions': 5},
            'EURUSD': {'multiplier': 1.2, 'threshold': 0.00005, 'max_positions': 3},
            'GBPUSD': {'multiplier': 0.8, 'threshold': 0.00006, 'max_positions': 2},
            'USDCHF': {'multiplier': 1.0, 'threshold': 0.00005, 'max_positions': 3}
        }
        
        # Tracking for circuit breakers
        self.daily_pnl = 0
        self.weekly_pnl = 0
        self.last_equity = initial_capital
        self.trade_timestamps = []
        
        # Partial profit taking
        self.quick_profit_target = 0.01   # 1% quick profit
        self.quick_profit_exit_pct = 0.5  # Exit 50%
        
        print("\nAggressive Sustainable Backtester initialized:")
        print(f"  Base risk: {self.base_risk_per_trade:.1%} per trade")
        print(f"  Max heat: {self.max_portfolio_heat:.1%}")
        print(f"  Daily loss limit: {self.daily_loss_limit:.1%}")
        print(f"  Kelly multiplier: {self.kelly_multiplier}x")
    
    def update_pnl_tracking(self, timestamp: pd.Timestamp):
        """Update daily and weekly P&L for circuit breakers."""
        current_equity = self.current_capital
        
        # Daily P&L reset
        if self.trade_timestamps:
            last_date = self.trade_timestamps[-1].date()
            current_date = timestamp.date()
            
            if current_date != last_date:
                # New day
                self.daily_pnl = 0
                self.last_equity = current_equity
            else:
                # Same day
                self.daily_pnl = (current_equity - self.last_equity) / self.last_equity
        
        # Weekly P&L (simplified - last 5 trading days)
        if len(self.equity_curve) > 30:  # 5 days * 6 bars
            weekly_start_equity = self.equity_curve[-30]
            self.weekly_pnl = (current_equity - weekly_start_equity) / weekly_start_equity
        
        self.trade_timestamps.append(timestamp)
    
    def check_circuit_breakers(self) -> bool:
        """Check if we should stop trading due to losses."""
        # Daily loss limit
        if self.daily_pnl <= -self.daily_loss_limit:
            return False  # Stop trading
        
        # Weekly loss limit (reduce, not stop)
        if self.weekly_pnl <= -self.weekly_loss_limit:
            return True  # Continue but with reduced size
        
        return True
    
    def calculate_position_size_aggressive(self, symbol: str, signal: dict, 
                                          current_price: float, atr: float, 
                                          volatility: float, current_bar: pd.Series) -> dict:
        """Calculate aggressive position size with smart controls."""
        
        # Check circuit breakers
        if not self.check_circuit_breakers():
            return {'units': 0, 'notional_value': 0, 'margin_required': 0}
        
        # Symbol-specific config
        symbol_config = self.symbol_configs.get(symbol, {})
        symbol_mult = symbol_config.get('multiplier', 1.0)
        
        # Check if we've hit symbol position limit
        symbol_positions = sum(1 for p in self.positions.values() if p['symbol'] == symbol)
        if symbol_positions >= symbol_config.get('max_positions', 3):
            return {'units': 0, 'notional_value': 0, 'margin_required': 0}
        
        # Base position size (aggressive)
        signal_quality = signal['quality']
        
        # Kelly-based sizing with multiplier
        if signal_quality > 0.8:
            base_size = self.base_risk_per_trade * self.kelly_multiplier * 2.0
        elif signal_quality > 0.7:
            base_size = self.base_risk_per_trade * self.kelly_multiplier * 1.5
        elif signal_quality > 0.6:
            base_size = self.base_risk_per_trade * self.kelly_multiplier
        else:
            base_size = self.base_risk_per_trade  # No multiplier for weak signals
        
        # Session adjustment
        session_mult = 1.0
        for session_name, mult in self.session_multipliers.items():
            if session_name in current_bar and current_bar[session_name] == 1:
                session_mult = mult
                break
        
        # Volatility adjustment (less conservative than base)
        if volatility > 0:
            vol_mult = min(0.015 / volatility, 2.0)
        else:
            vol_mult = 1.0
        
        # Weekly P&L adjustment
        if self.weekly_pnl < -0.05:
            pnl_mult = 0.5  # Half size if down 5%+
        elif self.weekly_pnl > 0.05:
            pnl_mult = 1.5  # Increase size if up 5%+
        else:
            pnl_mult = 1.0
        
        # Calculate final size
        position_pct = base_size * symbol_mult * session_mult * vol_mult * pnl_mult
        position_pct = min(position_pct, 0.05)  # Max 5% per position
        
        position_value = self.current_capital * position_pct
        position_value = max(self.min_position_size, position_value)
        
        # Calculate stops (tighter for aggressive trading)
        if atr > 0:
            stop_distance = atr * 1.5  # Tighter stop (1.5x ATR)
            target_distance = atr * 3.0  # Larger target (3x ATR)
            
            stop_loss_pct = stop_distance / current_price
            take_profit_pct = target_distance / current_price
        else:
            stop_loss_pct = volatility * 1.5
            take_profit_pct = volatility * 3.0
        
        # Minimum stops
        stop_loss_pct = max(stop_loss_pct, 0.0008)  # Min 0.08% (8 pips)
        take_profit_pct = max(take_profit_pct, 0.0024)  # Min 0.24% (24 pips)
        
        margin_required = position_value / self.account_leverage
        
        return {
            'units': position_value / current_price,
            'notional_value': position_value,
            'margin_required': margin_required,
            'stop_loss_pct': stop_loss_pct,
            'take_profit_pct': take_profit_pct,
            'position_pct': position_pct,
            'risk_amount': position_value * stop_loss_pct,
            'session_mult': session_mult,
            'symbol_mult': symbol_mult
        }
    
    def should_exit_position_aggressive(self, position: dict, current_bar: pd.Series,
                                      current_price: float, current_time: pd.Timestamp,
                                      atr: float) -> tuple:
        """Aggressive exit management - quick profits, fast stops."""
        
        # Calculate P&L
        if position['type'] == 'long':
            pnl_pct = (current_price - position['entry_price']) / position['entry_price']
        else:
            pnl_pct = (position['entry_price'] - current_price) / position['entry_price']
        
        # Quick partial profit taking
        if pnl_pct >= self.quick_profit_target and not position.get('partial_exit'):
            position['partial_exit'] = True
            # Return partial exit signal (would need position sizing adjustment)
            return True, 'partial_profit'
        
        # Time-based exit (more aggressive)
        hours_held = (current_time - position['entry_time']).total_seconds() / 3600
        
        # Exit non-performers quickly
        if hours_held > 24 and pnl_pct < 0.002:  # Less than 0.2% in 24h
            return True, 'time_stop'
        
        # Let big winners run but with trailing stop
        if pnl_pct >= 0.02:  # 2% profit
            if 'trailing_stop' not in position:
                # Initialize trailing stop
                if position['type'] == 'long':
                    position['trailing_stop'] = current_price * 0.99  # 1% trailing
                else:
                    position['trailing_stop'] = current_price * 1.01
            else:
                # Update trailing stop
                if position['type'] == 'long':
                    new_stop = current_price * 0.99
                    if new_stop > position['trailing_stop']:
                        position['trailing_stop'] = new_stop
                else:
                    new_stop = current_price * 1.01
                    if new_stop < position['trailing_stop']:
                        position['trailing_stop'] = new_stop
            
            # Check trailing stop
            if position['type'] == 'long' and current_price <= position['trailing_stop']:
                return True, 'trailing_stop'
            elif position['type'] == 'short' and current_price >= position['trailing_stop']:
                return True, 'trailing_stop'
        
        # Standard exits
        return super().should_exit_position_enhanced(position, current_bar, 
                                                   current_price, current_time, atr)
    
    def generate_signal(self, symbol: str, current_bar: pd.Series) -> dict:
        """Generate signal with multi-timeframe conviction scoring."""
        
        # Get base signal from parent class
        signal = super().generate_signal(symbol, current_bar)
        
        if signal['signal'] == 0:
            return signal
        
        # Add conviction scoring based on multiple factors
        conviction_score = signal['quality']
        
        # Trend alignment bonus
        if 'trend_strength_30' in current_bar:
            trend = current_bar['trend_strength_30']
            if (signal['signal'] == 1 and trend > 0.6) or \
               (signal['signal'] == -1 and trend < -0.6):
                conviction_score += 0.2
        
        # Momentum confirmation
        if 'rsi_14' in current_bar:
            rsi = current_bar['rsi_14']
            if (signal['signal'] == 1 and 30 < rsi < 70) or \
               (signal['signal'] == -1 and 30 < rsi < 70):
                conviction_score += 0.1
        
        # Session quality bonus
        for session in ['session_London2', 'session_NewYork1']:
            if session in current_bar and current_bar[session] == 1:
                conviction_score += 0.1
                break
        
        # Only take high conviction trades
        if conviction_score < 0.7:
            signal['signal'] = 0  # Skip low conviction
        else:
            signal['conviction'] = min(conviction_score, 1.0)
            signal['quality'] = signal['conviction']  # Use conviction as quality
        
        return signal
    
    def calculate_position_size_enhanced(self, symbol: str, signal_quality: float, 
                                       current_price: float, atr: float, 
                                       current_volatility: float) -> dict:
        """Override parent to use aggressive sizing."""
        # Use our aggressive sizing method with empty series for now
        current_bar = pd.Series()
        signal = {'quality': signal_quality}
        return self.calculate_position_size_aggressive(
            symbol, signal, current_price, atr, current_volatility, current_bar
        )
    
    def should_exit_position_enhanced(self, position: dict, current_bar: pd.Series,
                                    current_price: float, current_time: pd.Timestamp,
                                    atr: float) -> tuple:
        """Override parent to use aggressive exits."""
        return self.should_exit_position_aggressive(
            position, current_bar, current_price, current_time, atr
        )
    
    def _calculate_aggressive_metrics(self):
        """Calculate additional metrics for aggressive trading."""
        trades_df = pd.DataFrame(self.trades)
        
        # Exit reason analysis (more relevant than session for now)
        exit_reason_stats = trades_df.groupby('exit_reason').agg({
            'pnl': ['count', 'mean', lambda x: (x > 0).mean()],
            'holding_hours': 'mean'
        }).round(2)
        
        # Add to metrics
        self.metrics['exit_reason_analysis'] = exit_reason_stats.to_dict()
        self.metrics['partial_profits'] = len([t for t in self.trades 
                                              if t.get('exit_reason') == 'partial_profit'])
        self.metrics['time_stops'] = len([t for t in self.trades 
                                         if t.get('exit_reason') == 'time_stop'])
        
        print("\n\nAGGRESSIVE STRATEGY ANALYSIS")
        print("="*60)
        print("\nExit Reason Performance:")
        print(exit_reason_stats)
        
        # Symbol multiplier effectiveness
        symbol_stats = trades_df.groupby('symbol').agg({
            'pnl': ['count', 'sum', 'mean', lambda x: (x > 0).mean()]
        }).round(2)
        
        print("\n\nSymbol Performance with Multipliers:")
        for symbol in self.symbol_configs.keys():
            if symbol in symbol_stats.index:
                mult = self.symbol_configs[symbol]['multiplier']
                stats = symbol_stats.loc[symbol, 'pnl']
                print(f"{symbol} (mult={mult}x): "
                      f"{int(stats['count'])} trades, "
                      f"${stats['sum']:.2f} total, "
                      f"{stats['<lambda>']:.1%} win rate")
    
    def run_backtest(self, start_date: str, end_date: str):
        """Run aggressive sustainable backtest."""
        print("\n" + "="*80)
        print("AGGRESSIVE SUSTAINABLE 4-HOUR FOREX BACKTEST")
        print("="*80)
        
        # Run parent backtest
        super().run_backtest(start_date, end_date)
        
        # Add additional metrics
        if self.trades:
            self._calculate_aggressive_metrics()
    


def main():
    """Run aggressive sustainable backtest."""
    
    # Set environment for aggressive trading
    os.environ['FOREX_MIN_POSITION_SIZE_4H'] = '5000'
    os.environ['FOREX_MAX_POSITIONS_4H'] = '20'  # More positions allowed
    
    symbols = ['EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF']
    
    # Test period
    start_date = '2024-07-01'
    end_date = '2024-12-31'
    
    # Run backtest
    backtester = AggressiveSustainableBacktester(symbols, initial_capital=100000)
    
    # No need to override - methods are already properly defined in the class
    
    backtester.run_backtest(start_date, end_date)
    
    # Save results
    if backtester.trades:
        trades_df = pd.DataFrame(backtester.trades)
        trades_df.to_csv('output/aggressive_sustainable_trades.csv', index=False)
        
        with open('output/aggressive_sustainable_metrics.json', 'w') as f:
            json.dump(backtester.metrics, f, indent=2, default=str)
        
        print("\n✅ Results saved to:")
        print("  - output/aggressive_sustainable_trades.csv")
        print("  - output/aggressive_sustainable_metrics.json")

if __name__ == "__main__":
    main()