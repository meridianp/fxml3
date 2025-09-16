#!/usr/bin/env python
"""Ultimate aggressive backtester - targeting 50%+ annual returns."""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
import json
import os
from scripts.create_optimized_4h_backtester import Optimized4HBacktester

class UltimateAggressiveBacktester(Optimized4HBacktester):
    """Maximum aggression while maintaining some sanity."""
    
    def __init__(self, symbols: list, initial_capital: float = 100000):
        # Initialize parent first
        super().__init__(symbols, initial_capital)
        
        # ULTIMATE AGGRESSIVE SETTINGS
        self.min_position_size = 50000      # $50k minimum
        self.max_positions = 3              # Concentrate in fewer trades
        self.signal_quality_threshold = 0.6 # Take more signals
        
        # Risk settings
        self.risk_per_trade = 0.03          # 3% risk per trade
        self.max_portfolio_risk = 0.10      # 10% max portfolio risk
        
        # Aggressive exits
        self.quick_profit_target = 0.002    # 20 pips quick profit
        self.max_holding_hours = 24         # 24h max hold
        self.trailing_activation = 0.003    # Trail at 30 pips
        
        print("\nUltimate Aggressive Settings:")
        print(f"  Min Position: ${self.min_position_size:,}")
        print(f"  Risk per Trade: {self.risk_per_trade:.1%}")
        print(f"  Max Portfolio Risk: {self.max_portfolio_risk:.1%}")
    
    def calculate_position_size(self, symbol: str, signal_quality: float, 
                              volatility: float) -> dict:
        """Calculate aggressive position sizes."""
        
        # Base calculation: Risk 3% of capital per trade
        # With 20 pip stop (0.002), position size = risk / stop
        stop_loss_pips = 0.002  # 20 pips
        risk_amount = self.current_capital * self.risk_per_trade
        
        # Position size based on risk
        position_value = risk_amount / stop_loss_pips
        
        # Quality adjustment (only scale UP for great signals)
        if signal_quality > 0.8:
            position_value *= 1.5
        elif signal_quality > 0.7:
            position_value *= 1.2
        
        # Limit checks
        position_value = max(self.min_position_size, position_value)
        position_value = min(position_value, self.current_capital * 2)  # Max 200% of capital
        
        # Calculate margin needed
        margin_required = position_value / self.account_leverage
        
        # Check if we can afford it
        current_margin_used = sum(p.get('margin_required', 0) for p in self.positions.values())
        if current_margin_used + margin_required > self.current_capital * 0.8:  # Keep 20% buffer
            return {'units': 0, 'notional_value': 0, 'margin_required': 0}
        
        return {
            'units': position_value,
            'notional_value': position_value,
            'margin_required': margin_required,
            'stop_loss_pct': stop_loss_pips,
            'take_profit_pct': stop_loss_pips * 2,  # 2:1 RR
            'risk_amount': risk_amount
        }
    
    def should_exit_position(self, position: dict, current_bar: pd.Series, 
                           current_price: float, current_time: pd.Timestamp) -> tuple:
        """Aggressive exit management."""
        
        # Calculate P&L
        if position['type'] == 'long':
            pnl_pct = (current_price - position['entry_price']) / position['entry_price']
        else:
            pnl_pct = (position['entry_price'] - current_price) / position['entry_price']
        
        pnl_pips = pnl_pct * 10000  # Convert to pips
        
        # Quick scalp at 20 pips
        if pnl_pips >= 20 and not position.get('partial_taken'):
            position['partial_taken'] = True
            position['units'] *= 0.5  # Take half off
            return True, 'scalp_20_pips'
        
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
        
        # Time stop - aggressive
        hours_held = (current_time - position['entry_time']).total_seconds() / 3600
        if hours_held > self.max_holding_hours:
            return True, 'max_time_24h'
        
        # Stop loss check
        if pnl_pct <= -position['stop_loss_pct']:
            return True, 'stop_loss'
        
        # Take profit check
        if pnl_pct >= position['take_profit_pct']:
            return True, 'take_profit'
        
        return False, None
    
    def run_backtest(self, start_date: str, end_date: str):
        """Run ultimate aggressive backtest."""
        print("\n" + "="*80)
        print("ULTIMATE AGGRESSIVE FOREX BACKTEST")
        print("="*80)
        print(f"Period: {start_date} to {end_date}")
        print(f"Initial Capital: ${self.initial_capital:,.2f}")
        
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
        
        signals_evaluated = 0
        signals_taken = 0
        
        for i, timestamp in enumerate(all_timestamps):
            
            # Check exits
            for symbol in list(self.positions.keys()):
                if symbol in all_prices and timestamp in all_prices[symbol].index:
                    position = self.positions[symbol]
                    current_price = all_prices[symbol].loc[timestamp, 'close']
                    current_bar = all_data[symbol].loc[timestamp]
                    
                    should_exit, exit_reason = self.should_exit_position(
                        position, current_bar, current_price, timestamp
                    )
                    
                    if should_exit:
                        self._close_position(symbol, current_price, timestamp, exit_reason)
            
            # Evaluate new signals (only if room for positions)
            if len(self.positions) < self.max_positions:
                best_signal = None
                best_quality = 0
                
                for symbol in self.symbols:
                    if symbol in all_data and timestamp in all_data[symbol].index:
                        if symbol not in self.positions:
                            current_bar = all_data[symbol].loc[timestamp]
                            signal = self.generate_signal(symbol, current_bar)
                            
                            if signal['signal'] != 0 and signal['quality'] > self.signal_quality_threshold:
                                signals_evaluated += 1
                                
                                # Track best signal
                                if signal['quality'] > best_quality:
                                    best_quality = signal['quality']
                                    best_signal = {
                                        'symbol': symbol,
                                        'signal': signal,
                                        'price': all_prices[symbol].loc[timestamp, 'close'],
                                        'volatility': current_bar.get('volatility_12', 0.01)
                                    }
                
                # Take the best signal
                if best_signal:
                    signals_taken += 1
                    self._open_position(
                        best_signal['symbol'],
                        best_signal['signal']['signal'],
                        best_signal['price'],
                        timestamp,
                        best_signal['volatility']
                    )
            
            # Update equity
            self._update_equity(all_data, all_prices, timestamp)
            
            # Progress
            if (i + 1) % 150 == 0:
                current_pnl = (self.current_capital - self.initial_capital) / self.initial_capital
                print(f"  Day {(i+1)/6:.0f}: "
                      f"P&L: {current_pnl:+.1%}, "
                      f"Trades: {len(self.trades)}, "
                      f"Open: {len(self.positions)}")
        
        # Close remaining
        print("\nClosing remaining positions...")
        for symbol in list(self.positions.keys()):
            if symbol in all_prices:
                last_price = all_prices[symbol].iloc[-1]['close']
                self._close_position(symbol, last_price, all_timestamps[-1], 'end_of_test')
        
        # Results
        self._calculate_performance()
        self._generate_report(signals_evaluated, signals_taken)
        self._show_position_analysis()
    
    def _open_position(self, symbol: str, direction: int, price: float, 
                      timestamp: pd.Timestamp, volatility: float):
        """Open aggressive position."""
        
        # Get signal for quality
        signal_quality = 0.7  # Default if not available
        
        # Calculate position
        position_info = self.calculate_position_size(symbol, signal_quality, volatility)
        
        if position_info['units'] == 0:
            return
        
        # Open position
        self.positions[symbol] = {
            'symbol': symbol,
            'type': 'long' if direction == 1 else 'short',
            'entry_time': timestamp,
            'entry_price': price,
            'units': position_info['units'],
            'notional_value': position_info['notional_value'],
            'margin_required': position_info['margin_required'],
            'stop_loss_pct': position_info['stop_loss_pct'],
            'take_profit_pct': position_info['take_profit_pct'],
            'risk_amount': position_info['risk_amount'],
            'signal_quality': signal_quality  # Required by parent class
        }
    
    def _show_position_analysis(self):
        """Show detailed position analysis."""
        if not self.trades:
            return
        
        print("\n\nPOSITION SIZE ANALYSIS")
        print("="*60)
        
        positions = [t.get('notional_value', 0) for t in self.trades]
        risks = [t.get('risk_amount', 0) for t in self.trades]
        
        if positions[0] > 0:  # We have position data
            avg_position = np.mean(positions)
            max_position = np.max(positions)
            avg_risk = np.mean(risks)
            
            print(f"Average Position Size: ${avg_position:,.0f}")
            print(f"Max Position Size: ${max_position:,.0f}")
            print(f"As % of Capital: {avg_position/self.initial_capital:.1%}")
            print(f"Effective Leverage: {avg_position/self.initial_capital:.1f}x")
            print(f"\nAverage Risk per Trade: ${avg_risk:.0f}")
            print(f"Risk as % of Capital: {avg_risk/self.initial_capital:.1%}")


def main():
    """Run ultimate aggressive backtest."""
    
    symbols = ['EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF']
    
    # Test period
    start_date = '2024-07-01'
    end_date = '2024-12-31'
    
    # Run backtest
    backtester = UltimateAggressiveBacktester(symbols, initial_capital=100000)
    backtester.run_backtest(start_date, end_date)
    
    # Save results
    if backtester.trades:
        trades_df = pd.DataFrame(backtester.trades)
        trades_df.to_csv('output/ultimate_aggressive_trades.csv', index=False)
        
        # Print key stats
        print("\n\nFINAL STATISTICS")
        print("="*60)
        print(f"Total Return: {backtester.metrics['total_return']:+.1%}")
        print(f"Annualized: {backtester.metrics['total_return'] * 2:+.1%}")
        print(f"Per Month: {backtester.metrics['total_return'] / 6:+.1%}")
        print(f"Avg per Trade: ${trades_df['pnl'].mean():.2f}")

if __name__ == "__main__":
    main()