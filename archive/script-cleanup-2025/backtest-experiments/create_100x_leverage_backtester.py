#!/usr/bin/env python
"""Backtester designed for 100:1 leverage with micro lot capabilities."""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import os
from scripts.create_enhanced_backtester import Enhanced4HBacktester

class Leverage100XBacktester(Enhanced4HBacktester):
    """Backtester specifically designed for 100:1 leverage with micro lots."""
    
    def __init__(self, symbols: list, initial_capital: float = 100000):
        super().__init__(symbols, initial_capital)
        
        # 100:1 leverage parameters
        self.account_leverage = 100  # Changed from 40:1 to 100:1
        
        # With 100:1, $100k can control $10M
        # Risk management becomes CRITICAL
        
        # Position sizing parameters
        self.base_risk_per_trade = 0.01      # 1% risk per trade (conservative with high leverage)
        self.max_risk_per_trade = 0.02       # 2% max risk
        self.min_risk_per_trade = 0.005      # 0.5% min risk
        
        # Micro lot parameters (1 micro lot = 1,000 units)
        self.micro_lot_size = 1000
        self.min_position_units = 100        # 0.1 micro lots minimum
        
        # Maximum exposure limits
        self.max_total_exposure_pct = 5.0   # Max 5x account size (500% exposure)
        self.max_correlation_exposure = 3.0  # Max 3x on correlated pairs
        
        # Dynamic position sizing factors
        self.volatility_window = 20          # 20 bars for volatility calc
        self.momentum_window = 10            # 10 bars for momentum
        self.signal_quality_threshold = 0.6  # Minimum signal quality
        
        # Stop loss and take profit
        self.base_stop_distance = 0.0015     # 15 pips base stop
        self.min_stop_distance = 0.0010      # 10 pips minimum
        self.max_stop_distance = 0.0030      # 30 pips maximum
        self.risk_reward_ratio = 2.0         # Minimum 2:1 RR
        
        # Maximum positions
        self.max_positions = 8               # More positions with smaller size each
        self.max_positions_per_symbol = 2    # Pyramid up to 2 positions per symbol
        
        # Performance tracking
        self.hourly_pnl = {}
        self.session_performance = {
            'asian': {'trades': 0, 'pnl': 0},
            'london': {'trades': 0, 'pnl': 0},
            'ny': {'trades': 0, 'pnl': 0}
        }
        
        print("\n100:1 Leverage Backtester initialized")
        print(f"Account: ${self.initial_capital:,.0f}")
        print(f"Max Exposure: ${self.initial_capital * self.max_total_exposure_pct:,.0f}")
        print(f"Risk per trade: {self.base_risk_per_trade:.1%}")
        print(f"Min position: {self.min_position_units} units")
    
    def calculate_optimal_position_size(self, symbol: str, signal_quality: float,
                                      current_price: float, atr: float,
                                      current_volatility: float, 
                                      account_balance: float) -> dict:
        """Calculate position size optimized for 100:1 leverage."""
        
        # Step 1: Calculate stop distance based on ATR
        if atr > 0:
            stop_distance = np.clip(atr * 1.5, self.min_stop_distance, self.max_stop_distance)
        else:
            stop_distance = self.base_stop_distance
        
        # Step 2: Calculate base risk amount
        base_risk_amount = account_balance * self.base_risk_per_trade
        
        # Step 3: Adjust risk based on signal quality
        if signal_quality > 0.85:
            risk_multiplier = 2.0    # Double risk for excellent signals
        elif signal_quality > 0.75:
            risk_multiplier = 1.5
        elif signal_quality > 0.65:
            risk_multiplier = 1.0
        else:
            risk_multiplier = 0.5    # Half risk for weak signals
        
        # Step 4: Volatility adjustment
        # Lower volatility = larger positions, higher volatility = smaller positions
        normal_volatility = 0.001  # 10 pips per hour baseline
        if current_volatility > 0:
            volatility_factor = normal_volatility / current_volatility
            volatility_factor = np.clip(volatility_factor, 0.5, 2.0)
        else:
            volatility_factor = 1.0
        
        # Step 5: Calculate position units
        # Risk Amount = Position Size * Stop Distance
        # Position Size = Risk Amount / Stop Distance
        adjusted_risk = base_risk_amount * risk_multiplier * volatility_factor
        adjusted_risk = np.clip(adjusted_risk, 
                               account_balance * self.min_risk_per_trade,
                               account_balance * self.max_risk_per_trade)
        
        position_value = adjusted_risk / stop_distance
        position_units = position_value / current_price
        
        # Step 6: Round to nearest 100 units (0.1 micro lots)
        position_units = round(position_units / 100) * 100
        position_units = max(position_units, self.min_position_units)
        
        # Step 7: Check leverage constraints
        position_value = position_units * current_price
        margin_required = position_value / self.account_leverage
        
        # Step 8: Check total exposure
        current_exposure = self.calculate_total_exposure()
        new_total_exposure = current_exposure + position_value
        
        if new_total_exposure > account_balance * self.max_total_exposure_pct:
            # Scale down to fit within exposure limits
            available_exposure = (account_balance * self.max_total_exposure_pct) - current_exposure
            if available_exposure > 0:
                position_value = available_exposure
                position_units = round((position_value / current_price) / 100) * 100
                position_units = max(position_units, self.min_position_units)
            else:
                return {
                    'units': 0,
                    'notional_value': 0,
                    'margin_required': 0,
                    'stop_loss_pct': 0,
                    'take_profit_pct': 0,
                    'position_pct': 0,
                    'risk_amount': 0
                }
        
        # Recalculate final values
        position_value = position_units * current_price
        margin_required = position_value / self.account_leverage
        actual_risk = position_value * stop_distance
        
        # Calculate take profit based on risk/reward
        take_profit_distance = stop_distance * self.risk_reward_ratio
        
        return {
            'units': position_units,
            'notional_value': position_value,
            'margin_required': margin_required,
            'stop_loss_pct': stop_distance,
            'take_profit_pct': take_profit_distance,
            'risk_amount': actual_risk,
            'risk_pct': actual_risk / account_balance,
            'position_size_lots': position_units / self.micro_lot_size,
            'leverage_used': position_value / margin_required,
            'position_pct': position_value / account_balance
        }
    
    def calculate_total_exposure(self) -> float:
        """Calculate total market exposure across all positions."""
        total = 0
        for position in self.positions.values():
            total += position.get('notional_value', 0)
        return total
    
    def calculate_correlation_exposure(self, symbol: str) -> float:
        """Calculate exposure to correlated instruments."""
        # Define correlation groups
        correlation_groups = {
            'USD_LONG': ['USDJPY', 'USDCHF'],
            'USD_SHORT': ['EURUSD', 'GBPUSD'],
            'EUR': ['EURUSD'],
            'GBP': ['GBPUSD'],
            'JPY': ['USDJPY'],
            'CHF': ['USDCHF']
        }
        
        # Find which groups this symbol belongs to
        symbol_groups = []
        for group, symbols in correlation_groups.items():
            if symbol in symbols:
                symbol_groups.append(group)
        
        # Calculate total exposure in correlated positions
        correlated_exposure = 0
        for pos_symbol, position in self.positions.items():
            for group, symbols in correlation_groups.items():
                if group in symbol_groups and pos_symbol in symbols:
                    correlated_exposure += position.get('notional_value', 0)
                    break
        
        return correlated_exposure
    
    def can_open_position(self, symbol: str, position_value: float) -> bool:
        """Check if we can open a new position given exposure limits."""
        # Check total exposure
        current_exposure = self.calculate_total_exposure()
        if current_exposure + position_value > self.current_capital * self.max_total_exposure_pct:
            return False
        
        # Check correlation exposure
        correlation_exposure = self.calculate_correlation_exposure(symbol)
        if correlation_exposure + position_value > self.current_capital * self.max_correlation_exposure:
            return False
        
        # Check positions per symbol
        symbol_positions = sum(1 for s in self.positions if s == symbol)
        if symbol_positions >= self.max_positions_per_symbol:
            return False
        
        # Check total positions
        if len(self.positions) >= self.max_positions:
            return False
        
        return True
    
    def calculate_position_size_enhanced(self, symbol: str, signal_quality: float,
                                       current_price: float, atr: float,
                                       current_volatility: float) -> dict:
        """Enhanced position sizing for 100:1 leverage."""
        
        # Get optimal position size
        position_info = self.calculate_optimal_position_size(
            symbol, signal_quality, current_price, atr,
            current_volatility, self.current_capital
        )
        
        # Check if we can open this position
        if position_info['units'] > 0:
            if not self.can_open_position(symbol, position_info['notional_value']):
                # Return full structure with 0 units
                return {
                    'units': 0,
                    'notional_value': 0,
                    'margin_required': 0,
                    'stop_loss_pct': 0,
                    'take_profit_pct': 0,
                    'position_pct': 0,
                    'risk_amount': 0
                }
        
        return position_info
    
    def get_trading_session(self, timestamp: pd.Timestamp) -> str:
        """Determine current trading session."""
        hour = timestamp.hour
        
        # Forex sessions (UTC)
        if 23 <= hour or hour < 8:  # 11 PM - 8 AM UTC
            return 'asian'
        elif 8 <= hour < 16:  # 8 AM - 4 PM UTC
            return 'london'
        else:  # 4 PM - 11 PM UTC
            return 'ny'
    
    def should_exit_position_enhanced(self, position: dict, current_bar: pd.Series,
                                    current_price: float, current_time: pd.Timestamp,
                                    atr: float) -> tuple:
        """Enhanced exit logic for 100:1 leverage positions."""
        
        # Calculate P&L
        if position['type'] == 'long':
            pnl_pct = (current_price - position['entry_price']) / position['entry_price']
        else:
            pnl_pct = (position['entry_price'] - current_price) / position['entry_price']
        
        # 1. Stop loss - CRITICAL with 100:1 leverage
        if pnl_pct <= -position['stop_loss_pct']:
            return True, 'stop_loss'
        
        # 2. Take profit
        if pnl_pct >= position['take_profit_pct']:
            return True, 'take_profit'
        
        # 3. Trailing stop for profits > 50% of target
        profit_progress = pnl_pct / position['take_profit_pct']
        if profit_progress > 0.5:
            # Move stop to breakeven
            if not position.get('breakeven_set'):
                position['breakeven_set'] = True
                position['trailing_stop'] = position['entry_price']
            
            # Trail the stop
            if profit_progress > 0.75:
                trail_distance = position['stop_loss_pct'] * 0.5  # Trail by half the original stop
                if position['type'] == 'long':
                    new_stop = current_price - (current_price * trail_distance)
                    position['trailing_stop'] = max(position.get('trailing_stop', 0), new_stop)
                    if current_price <= position['trailing_stop']:
                        return True, 'trailing_stop'
                else:
                    new_stop = current_price + (current_price * trail_distance)
                    position['trailing_stop'] = min(position.get('trailing_stop', float('inf')), new_stop)
                    if current_price >= position['trailing_stop']:
                        return True, 'trailing_stop'
        
        # 4. Time-based exit for small profits/losses
        hours_held = (current_time - position['entry_time']).total_seconds() / 3600
        if hours_held > 8 and abs(pnl_pct) < 0.001:  # Less than 10 pips after 8 hours
            return True, 'time_exit_8h'
        
        # 5. Session change exit (optional)
        current_session = self.get_trading_session(current_time)
        entry_session = self.get_trading_session(position['entry_time'])
        if current_session != entry_session and hours_held > 4:
            if abs(pnl_pct) < position['stop_loss_pct'] * 0.5:  # Less than half the risk
                return True, 'session_change'
        
        return False, None
    
    def _open_position_enhanced(self, symbol: str, signal: dict, price: float,
                               timestamp: pd.Timestamp, volatility: float, atr: float):
        """Override to track session performance."""
        # Call parent method
        super()._open_position_enhanced(symbol, signal, price, timestamp, volatility, atr)
        
        # Track session if position was opened
        if symbol in self.positions:
            session = self.get_trading_session(timestamp)
            self.positions[symbol]['session'] = session
    
    def _close_position(self, symbol: str, price: float, timestamp: pd.Timestamp, reason: str):
        """Override to track session performance."""
        if symbol in self.positions:
            position = self.positions[symbol]
            
            # Calculate P&L
            if position['type'] == 'long':
                pnl = (price - position['entry_price']) * position['units']
            else:
                pnl = (position['entry_price'] - price) * position['units']
            
            # Track session performance
            session = position.get('session', 'unknown')
            if session in self.session_performance:
                self.session_performance[session]['trades'] += 1
                self.session_performance[session]['pnl'] += pnl
            
            # Track hourly P&L
            self.hourly_pnl[timestamp] = self.hourly_pnl.get(timestamp, 0) + pnl
        
        # Call parent method
        super()._close_position(symbol, price, timestamp, reason)
    
    def _generate_report(self, signals_evaluated: int, signals_taken: int):
        """Generate comprehensive report for 100:1 leverage trading."""
        # Call parent report first
        super()._generate_report(signals_evaluated, signals_taken)
        
        if not self.trades:
            return
        
        print("\n\n100:1 LEVERAGE ANALYSIS")
        print("="*60)
        
        trades_df = pd.DataFrame(self.trades)
        
        # Position size analysis
        if 'units' in trades_df.columns:
            avg_units = trades_df['units'].mean()
            avg_lots = avg_units / self.micro_lot_size
            max_units = trades_df['units'].max()
            max_lots = max_units / self.micro_lot_size
            
            print(f"Average Position: {avg_units:,.0f} units ({avg_lots:.2f} micro lots)")
            print(f"Max Position: {max_units:,.0f} units ({max_lots:.2f} micro lots)")
        
        # Leverage usage
        if 'notional_value' in trades_df.columns:
            avg_notional = trades_df['notional_value'].mean()
            max_notional = trades_df['notional_value'].max()
            avg_leverage = avg_notional / (self.initial_capital / self.account_leverage)
            
            print(f"\nAverage Notional: ${avg_notional:,.0f}")
            print(f"Max Notional: ${max_notional:,.0f}")
            print(f"Average Leverage Used: {avg_leverage:.1f}x")
        
        # Risk analysis
        if 'risk_amount' in trades_df.columns:
            avg_risk = trades_df['risk_amount'].mean()
            max_risk = trades_df['risk_amount'].max()
            avg_risk_pct = avg_risk / self.initial_capital
            
            print(f"\nAverage Risk per Trade: ${avg_risk:.2f} ({avg_risk_pct:.2%})")
            print(f"Max Risk per Trade: ${max_risk:.2f}")
        
        # Session analysis
        print("\n\nSESSION PERFORMANCE")
        print("-"*40)
        for session, data in self.session_performance.items():
            if data['trades'] > 0:
                avg_pnl = data['pnl'] / data['trades']
                print(f"{session.capitalize()}: {data['trades']} trades, "
                      f"Total: ${data['pnl']:.2f}, Avg: ${avg_pnl:.2f}")
        
        # Hourly P&L distribution
        if self.hourly_pnl:
            print("\n\nHOURLY P&L DISTRIBUTION")
            print("-"*40)
            hourly_summary = {}
            for timestamp, pnl in self.hourly_pnl.items():
                hour = timestamp.hour
                if hour not in hourly_summary:
                    hourly_summary[hour] = []
                hourly_summary[hour].append(pnl)
            
            best_hours = []
            for hour in sorted(hourly_summary.keys()):
                total_pnl = sum(hourly_summary[hour])
                avg_pnl = total_pnl / len(hourly_summary[hour])
                if total_pnl > 0:
                    best_hours.append((hour, total_pnl, avg_pnl))
            
            # Show top 5 profitable hours
            best_hours.sort(key=lambda x: x[1], reverse=True)
            print("Top 5 Profitable Hours (UTC):")
            for hour, total, avg in best_hours[:5]:
                print(f"  {hour:02d}:00 - Total: ${total:.2f}, Avg: ${avg:.2f}")


def main():
    """Run 100:1 leverage backtest."""
    
    symbols = ['EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF']
    
    # Test period
    start_date = '2024-07-01'
    end_date = '2024-12-31'
    
    print("="*80)
    print("100:1 LEVERAGE FOREX BACKTEST")
    print("="*80)
    print("Using micro lots with 100:1 leverage for optimal position sizing")
    print("="*80)
    
    # Run backtest
    backtester = Leverage100XBacktester(symbols, initial_capital=100000)
    backtester.run_backtest(start_date, end_date)
    
    # Save results
    if backtester.trades:
        trades_df = pd.DataFrame(backtester.trades)
        trades_df.to_csv('output/leverage_100x_trades.csv', index=False)
        
        with open('output/leverage_100x_metrics.json', 'w') as f:
            json.dump(backtester.metrics, f, indent=2, default=str)
        
        print("\n✅ Results saved to:")
        print("  - output/leverage_100x_trades.csv")
        print("  - output/leverage_100x_metrics.json")

if __name__ == "__main__":
    main()