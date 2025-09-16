#!/usr/bin/env python
"""Properly leveraged backtester that actually uses the 40:1 forex leverage."""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import os
from scripts.create_enhanced_backtester import Enhanced4HBacktester

class ProperlyLeveragedBacktester(Enhanced4HBacktester):
    """Backtester that properly uses forex leverage for real returns."""
    
    def __init__(self, symbols: list, initial_capital: float = 100000):
        super().__init__(symbols, initial_capital)
        
        # PROPERLY AGGRESSIVE PARAMETERS
        self.min_position_size = 25000  # $25k minimum (was $5k)
        self.base_position_pct = 0.25   # 25% of capital base position
        self.max_position_pct = 0.50    # 50% of capital max position
        
        # With 40:1 leverage, we can control $4M with $100k
        # Let's use a reasonable portion of that
        self.target_leverage_usage = 10  # Use 10x leverage (25% of available)
        
        # Adjusted risk parameters for larger positions
        self.max_portfolio_heat = 0.15   # 15% total heat
        self.stop_loss_pct = 0.002       # 0.2% = 20 pips (tighter stops)
        self.take_profit_pct = 0.004     # 0.4% = 40 pips
        
        # Fewer but better trades
        self.signal_quality_threshold = 0.65  # Higher threshold
        self.min_conviction = 0.75           # Only high conviction
        
        # Position limits
        self.max_positions = 4  # Fewer positions, larger size
        
        print("\nProperly Leveraged Backtester initialized:")
        print(f"  Min Position Size: ${self.min_position_size:,.0f}")
        print(f"  Base Position: {self.base_position_pct:.0%} of capital")
        print(f"  Target Leverage: {self.target_leverage_usage}x")
        print(f"  Max Positions: {self.max_positions}")
        print(f"  Signal Quality: >{self.signal_quality_threshold:.0%}")
    
    def calculate_position_size_enhanced(self, symbol: str, signal_quality: float, 
                                       current_price: float, atr: float, 
                                       current_volatility: float) -> dict:
        """Calculate properly leveraged position sizes."""
        
        # Start with base percentage of capital
        base_position_value = self.current_capital * self.base_position_pct
        
        # Quality multiplier (only scale up, never down)
        if signal_quality > 0.85:
            quality_mult = 2.0
        elif signal_quality > 0.75:
            quality_mult = 1.5
        elif signal_quality > 0.65:
            quality_mult = 1.0
        else:
            # Don't take low quality trades
            return {'units': 0, 'notional_value': 0, 'margin_required': 0}
        
        # Volatility adjustment (less conservative)
        if current_volatility < 0.001:  # Very low vol
            vol_mult = 1.5
        elif current_volatility < 0.002:  # Normal vol
            vol_mult = 1.0
        else:  # High vol
            vol_mult = 0.7
        
        # Calculate position size
        position_value = base_position_value * quality_mult * vol_mult
        
        # Apply limits
        position_value = max(self.min_position_size, position_value)
        position_value = min(position_value, self.current_capital * self.max_position_pct)
        
        # Calculate actual leverage used
        total_positions_value = sum(p.get('notional_value', 0) for p in self.positions.values())
        new_total = total_positions_value + position_value
        leverage_used = new_total / self.current_capital
        
        # Don't exceed target leverage
        if leverage_used > self.target_leverage_usage:
            position_value = (self.target_leverage_usage * self.current_capital) - total_positions_value
            if position_value < self.min_position_size:
                return {'units': 0, 'notional_value': 0, 'margin_required': 0}
        
        # Calculate stops and targets (tighter for larger positions)
        if atr > 0:
            stop_distance = atr * 1.0  # 1x ATR stop
            target_distance = atr * 2.0  # 2x ATR target
            
            stop_loss_pct = stop_distance / current_price
            take_profit_pct = target_distance / current_price
        else:
            stop_loss_pct = self.stop_loss_pct
            take_profit_pct = self.take_profit_pct
        
        # Ensure minimum risk/reward
        stop_loss_pct = max(stop_loss_pct, 0.001)  # Min 10 pips
        take_profit_pct = max(take_profit_pct, stop_loss_pct * 2)  # Min 2:1
        
        # Calculate margin (what we actually need in our account)
        margin_required = position_value / self.account_leverage
        
        # Risk calculation
        risk_amount = position_value * stop_loss_pct
        risk_pct = risk_amount / self.current_capital
        
        # Don't risk more than 2% per trade
        if risk_pct > 0.02:
            # Scale down position to meet risk limit
            position_value = (0.02 * self.current_capital) / stop_loss_pct
            margin_required = position_value / self.account_leverage
            risk_amount = position_value * stop_loss_pct
        
        return {
            'units': position_value / current_price,
            'notional_value': position_value,
            'margin_required': margin_required,
            'stop_loss_pct': stop_loss_pct,
            'take_profit_pct': take_profit_pct,
            'position_pct': position_value / self.current_capital,
            'risk_amount': risk_amount,
            'leverage_used': position_value / margin_required
        }
    
    def generate_signal(self, symbol: str, features: pd.Series) -> dict:
        """Generate high-conviction signals only."""
        # Get base signal
        signal = super().generate_signal(symbol, features)
        
        if signal['signal'] == 0:
            return signal
        
        # Additional conviction filters
        conviction_score = signal['quality']
        
        # Trend strength filter
        if 'trend_strength_30' in features:
            trend = abs(features['trend_strength_30'])
            if trend > 0.7:
                conviction_score += 0.15
        
        # Momentum confirmation
        if 'rsi_14' in features:
            rsi = features['rsi_14']
            if (signal['signal'] == 1 and 40 < rsi < 60) or \
               (signal['signal'] == -1 and 40 < rsi < 60):
                conviction_score += 0.10
        
        # Only take high conviction trades
        if conviction_score < self.min_conviction:
            signal['signal'] = 0
            signal['filtered_reason'] = 'low_conviction'
        else:
            signal['conviction'] = min(conviction_score, 1.0)
            signal['quality'] = signal['conviction']
        
        return signal
    
    def should_exit_position_enhanced(self, position: dict, current_bar: pd.Series,
                                    current_price: float, current_time: pd.Timestamp,
                                    atr: float) -> tuple:
        """Exit management for leveraged positions."""
        
        # Calculate P&L
        if position['type'] == 'long':
            pnl_pct = (current_price - position['entry_price']) / position['entry_price']
        else:
            pnl_pct = (position['entry_price'] - current_price) / position['entry_price']
        
        # Quick profit taking on leveraged positions
        if pnl_pct >= 0.002:  # 0.2% = 20 pips
            # Take 50% profit quickly
            if not position.get('partial_exit'):
                position['partial_exit'] = True
                return True, 'quick_profit_20pips'
        
        # Breakeven stop after 10 pips profit
        if pnl_pct >= 0.001 and not position.get('breakeven_set'):
            position['breakeven_set'] = True
            position['stop_loss_pct'] = 0  # Move stop to breakeven
        
        # Time-based exit (tighter for leveraged positions)
        hours_held = (current_time - position['entry_time']).total_seconds() / 3600
        
        if hours_held > 12 and pnl_pct < 0.001:  # 12 hours, less than 10 pips
            return True, 'time_stop_12h'
        
        # Standard exits
        return super().should_exit_position_enhanced(position, current_bar, 
                                                   current_price, current_time, atr)
    
    def _generate_report(self, signals_evaluated: int, signals_taken: int):
        """Enhanced report showing leverage usage."""
        # Call parent report
        super()._generate_report(signals_evaluated, signals_taken)
        
        # Add leverage analysis
        if self.trades:
            trades_df = pd.DataFrame(self.trades)
            
            print("\n\nLEVERAGE ANALYSIS")
            print("="*60)
            
            # Average position size
            if 'notional_value' in self.trades[0]:
                positions = [t.get('notional_value', 0) for t in self.trades]
                avg_position = np.mean(positions)
                max_position = np.max(positions)
                
                print(f"Average Position Size: ${avg_position:,.0f}")
                print(f"Max Position Size: ${max_position:,.0f}")
                print(f"Average as % of Capital: {avg_position/self.initial_capital:.1%}")
                
                # Leverage usage
                avg_leverage = avg_position / (self.initial_capital / self.account_leverage)
                print(f"Average Leverage Used: {avg_leverage:.1f}x")
            
            # Risk per trade
            if 'risk_amount' in self.trades[0]:
                risks = [t.get('risk_amount', 0) for t in self.trades]
                avg_risk = np.mean(risks)
                print(f"\nAverage Risk per Trade: ${avg_risk:.2f}")
                print(f"Risk as % of Capital: {avg_risk/self.initial_capital:.2%}")


def main():
    """Run properly leveraged backtest."""
    
    symbols = ['EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF']
    
    # Test period
    start_date = '2024-07-01'
    end_date = '2024-12-31'
    
    print("="*80)
    print("PROPERLY LEVERAGED FOREX BACKTEST")
    print("="*80)
    print("Using leverage correctly for real returns!")
    print("="*80)
    
    # Run backtest
    backtester = ProperlyLeveragedBacktester(symbols, initial_capital=100000)
    backtester.run_backtest(start_date, end_date)
    
    # Save results
    if backtester.trades:
        trades_df = pd.DataFrame(backtester.trades)
        trades_df.to_csv('output/properly_leveraged_trades.csv', index=False)
        
        with open('output/properly_leveraged_metrics.json', 'w') as f:
            json.dump(backtester.metrics, f, indent=2, default=str)
        
        print("\n✅ Results saved to:")
        print("  - output/properly_leveraged_trades.csv")
        print("  - output/properly_leveraged_metrics.json")

if __name__ == "__main__":
    main()