#!/usr/bin/env python
"""Enhanced backtester with dynamic position sizing and better exit strategies."""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import joblib
import os
from dotenv import load_dotenv
from scripts.create_optimized_4h_backtester import Optimized4HBacktester

load_dotenv()

class Enhanced4HBacktester(Optimized4HBacktester):
    """Enhanced backtester with volatility-based sizing and better exits."""
    
    def __init__(self, symbols: list, initial_capital: float = 100000):
        super().__init__(symbols, initial_capital)
        
        # Enhanced settings
        self.use_volatility_sizing = True
        self.use_atr_stops = True
        self.use_trailing_stops = True
        self.use_momentum_exits = True
        
        # Risk management
        self.max_risk_per_trade = 0.01  # 1% max risk
        self.portfolio_heat = 0.0  # Track total portfolio risk
        self.max_portfolio_heat = 0.06  # 6% max portfolio risk
        
        # Enhanced exit parameters
        self.atr_stop_multiplier = 2.0  # 2x ATR for stops
        self.atr_target_multiplier = 3.0  # 3x ATR for targets
        self.trailing_stop_activation = 0.01  # Activate at 1% profit
        self.trailing_stop_distance = 0.005  # Trail by 0.5%
        
        print("\nEnhanced 4H Backtester initialized:")
        print(f"  Volatility-based sizing: {self.use_volatility_sizing}")
        print(f"  ATR stops: {self.use_atr_stops}")
        print(f"  Trailing stops: {self.use_trailing_stops}")
        print(f"  Max portfolio heat: {self.max_portfolio_heat:.1%}")
    
    def calculate_atr(self, price_data: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate Average True Range."""
        high = price_data['high']
        low = price_data['low']
        close = price_data['close']
        
        # True Range
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # ATR
        atr = tr.rolling(window=period).mean()
        return atr
    
    def calculate_position_size_enhanced(self, symbol: str, signal_quality: float, 
                                       current_price: float, atr: float, 
                                       current_volatility: float) -> dict:
        """Enhanced position sizing with volatility adjustment."""
        
        # Base position size from Kelly Criterion approximation
        # Position size = (Win% - Loss%) / (Win/Loss ratio)
        # Assuming 52% win rate and 1.4:1 reward/risk from backtest
        kelly_fraction = (0.52 - 0.48) / 1.4  # ~0.028 or 2.8%
        
        # Scale by signal quality
        quality_multiplier = signal_quality * 2  # 0.5-1.0 quality -> 1.0-2.0 multiplier
        
        # Volatility adjustment (inverse relationship)
        # Normal volatility for forex ~0.5-1% daily, ~0.25-0.5% for 4H
        normal_volatility = 0.003  # 0.3% for 4H
        vol_ratio = normal_volatility / max(current_volatility, 0.001)
        vol_multiplier = np.clip(vol_ratio, 0.5, 2.0)  # Limit adjustment
        
        # Portfolio heat adjustment
        heat_remaining = max(0, self.max_portfolio_heat - self.portfolio_heat)
        heat_multiplier = min(1.0, heat_remaining / self.max_risk_per_trade)
        
        # Calculate position size as % of capital
        position_pct = kelly_fraction * quality_multiplier * vol_multiplier * heat_multiplier
        position_pct = min(position_pct, 0.1)  # Max 10% per position
        
        # Convert to units
        position_value = self.current_capital * position_pct
        position_value = max(self.min_position_size, position_value)
        
        # Calculate stops and targets based on ATR
        if self.use_atr_stops and atr > 0:
            stop_distance = atr * self.atr_stop_multiplier
            target_distance = atr * self.atr_target_multiplier
            
            stop_loss_pct = stop_distance / current_price
            take_profit_pct = target_distance / current_price
        else:
            # Fallback to volatility-based stops
            stop_loss_pct = current_volatility * 2
            take_profit_pct = current_volatility * 3
        
        # Ensure minimum stop distance
        stop_loss_pct = max(stop_loss_pct, 0.001)  # Min 0.1%
        take_profit_pct = max(take_profit_pct, 0.002)  # Min 0.2%
        
        # Calculate margin
        margin_required = position_value / self.account_leverage
        
        return {
            'units': position_value / current_price,
            'notional_value': position_value,
            'margin_required': margin_required,
            'stop_loss_pct': stop_loss_pct,
            'take_profit_pct': take_profit_pct,
            'position_pct': position_pct,
            'risk_amount': position_value * stop_loss_pct
        }
    
    def should_exit_position_enhanced(self, position: dict, current_bar: pd.Series,
                                    current_price: float, current_time: pd.Timestamp,
                                    atr: float) -> tuple:
        """Enhanced exit logic with trailing stops and momentum exits."""
        
        # First check basic exits
        basic_exit, basic_reason = super().should_exit_position(
            position, current_bar, current_price, current_time
        )
        
        if basic_exit:
            return basic_exit, basic_reason
        
        # Calculate current P&L
        if position['type'] == 'long':
            pnl_pct = (current_price - position['entry_price']) / position['entry_price']
        else:
            pnl_pct = (position['entry_price'] - current_price) / position['entry_price']
        
        # Trailing stop logic
        if self.use_trailing_stops and pnl_pct >= self.trailing_stop_activation:
            # Update trailing stop if needed
            if 'trailing_stop' not in position:
                # Initialize trailing stop
                if position['type'] == 'long':
                    position['trailing_stop'] = current_price * (1 - self.trailing_stop_distance)
                else:
                    position['trailing_stop'] = current_price * (1 + self.trailing_stop_distance)
            else:
                # Update trailing stop if price moved favorably
                if position['type'] == 'long':
                    new_stop = current_price * (1 - self.trailing_stop_distance)
                    if new_stop > position['trailing_stop']:
                        position['trailing_stop'] = new_stop
                else:
                    new_stop = current_price * (1 + self.trailing_stop_distance)
                    if new_stop < position['trailing_stop']:
                        position['trailing_stop'] = new_stop
            
            # Check if trailing stop hit
            if position['type'] == 'long' and current_price <= position['trailing_stop']:
                return True, 'trailing_stop'
            elif position['type'] == 'short' and current_price >= position['trailing_stop']:
                return True, 'trailing_stop'
        
        # Momentum-based exit (exit if momentum reverses)
        if self.use_momentum_exits and 'rsi_14' in current_bar:
            rsi = current_bar['rsi_14']
            
            # Exit longs if RSI > 70 and declining
            if position['type'] == 'long' and rsi > 70:
                if 'last_rsi' in position and rsi < position['last_rsi']:
                    return True, 'momentum_exit'
            
            # Exit shorts if RSI < 30 and rising
            elif position['type'] == 'short' and rsi < 30:
                if 'last_rsi' in position and rsi > position['last_rsi']:
                    return True, 'momentum_exit'
            
            position['last_rsi'] = rsi
        
        # Dynamic take profit based on volatility
        if atr > 0:
            dynamic_target = atr * self.atr_target_multiplier / position['entry_price']
            if pnl_pct >= dynamic_target:
                return True, 'dynamic_target'
        
        return False, None
    
    def run_backtest(self, start_date: str, end_date: str):
        """Run enhanced backtest with improved position sizing and exits."""
        print("\n" + "="*80)
        print("ENHANCED 4-HOUR FOREX BACKTEST")
        print("="*80)
        print(f"Period: {start_date} to {end_date}")
        print(f"Initial Capital: ${self.initial_capital:,.2f}")
        
        # Load all data - both features and prices
        all_data = {}
        all_prices = {}
        all_atr = {}
        
        for symbol in self.symbols:
            # Load preprocessed features
            df_features = self.load_4h_data(symbol)
            
            # Load raw price data
            df_prices = self.load_4h_price_data(symbol, start_date, end_date)
            
            if df_features is not None and df_prices is not None:
                # Filter date range for features
                df_features = df_features[(df_features.index >= start_date) & (df_features.index <= end_date)]
                
                # Calculate ATR
                atr = self.calculate_atr(df_prices)
                
                # Align the datasets by index
                common_index = df_features.index.intersection(df_prices.index)
                
                if len(common_index) > 0:
                    all_data[symbol] = df_features.loc[common_index]
                    all_prices[symbol] = df_prices.loc[common_index]
                    all_atr[symbol] = atr.loc[common_index]
                    print(f"  ✅ {symbol}: {len(common_index)} 4H bars ({len(common_index)/6:.1f} days)")
                else:
                    print(f"  ⚠️  {symbol}: No overlapping data between features and prices")
            else:
                if df_features is None:
                    print(f"  ❌ {symbol}: No feature data available")
                if df_prices is None:
                    print(f"  ❌ {symbol}: No price data available")
        
        if not all_data:
            print("❌ No data available for backtesting")
            return
        
        # Get all 4H timestamps
        all_timestamps = sorted(set().union(*[set(df.index) for df in all_data.values()]))
        print(f"\nProcessing {len(all_timestamps)} 4H bars...")
        
        # Process each 4H bar
        signals_evaluated = 0
        signals_taken = 0
        
        for i, timestamp in enumerate(all_timestamps):
            
            # Update portfolio heat
            self.portfolio_heat = sum(p.get('risk_amount', 0) / self.current_capital 
                                    for p in self.positions.values())
            
            # First, check exits for existing positions
            for symbol in list(self.positions.keys()):
                if symbol in all_data and timestamp in all_data[symbol].index:
                    position = self.positions[symbol]
                    current_bar = all_data[symbol].loc[timestamp]
                    current_price = all_prices[symbol].loc[timestamp, 'close']
                    current_atr = all_atr[symbol].loc[timestamp] if timestamp in all_atr[symbol].index else 0
                    
                    should_exit, exit_reason = self.should_exit_position_enhanced(
                        position, current_bar, current_price, timestamp, current_atr
                    )
                    
                    if should_exit:
                        self._close_position(symbol, current_price, timestamp, exit_reason)
            
            # Then, evaluate new signals
            signal_candidates = []
            
            for symbol in self.symbols:
                if symbol in all_data and timestamp in all_data[symbol].index:
                    if symbol not in self.positions:  # No existing position
                        current_bar = all_data[symbol].loc[timestamp]
                        current_price = all_prices[symbol].loc[timestamp, 'close']
                        current_atr = all_atr[symbol].loc[timestamp] if timestamp in all_atr[symbol].index else 0
                        signal = self.generate_signal(symbol, current_bar)
                        
                        if signal['signal'] != 0:
                            signals_evaluated += 1
                            
                            # Calculate volatility
                            if 'volatility_12' in current_bar:
                                volatility = current_bar['volatility_12']
                            else:
                                volatility = 0.01  # Default 1%
                            
                            signal_candidates.append({
                                'symbol': symbol,
                                'signal': signal,
                                'price': current_price,
                                'volatility': volatility,
                                'bar': current_bar,
                                'atr': current_atr
                            })
            
            # Sort by quality and take best signals up to position limit
            signal_candidates.sort(key=lambda x: x['signal']['quality'], reverse=True)
            
            # Consider portfolio heat when determining how many positions to open
            positions_to_open = 0
            for candidate in signal_candidates:
                if len(self.positions) >= self.max_positions:
                    break
                
                # Check if we have room for more risk
                if self.portfolio_heat < self.max_portfolio_heat:
                    if candidate['signal']['quality'] >= self.signal_quality_threshold:
                        positions_to_open += 1
                        signals_taken += 1
                        self._open_position_enhanced(
                            candidate['symbol'],
                            candidate['signal'],
                            candidate['price'],
                            timestamp,
                            candidate['volatility'],
                            candidate['atr']
                        )
            
            # Update equity
            self._update_equity(all_data, all_prices, timestamp)
            
            # Progress update
            if (i + 1) % 300 == 0:  # Every ~50 days
                days_processed = (i + 1) / 6
                print(f"  Processed {days_processed:.0f} days, "
                      f"Equity: ${self.current_capital:,.2f}, "
                      f"Trades: {len(self.trades)}, "
                      f"Positions: {len(self.positions)}, "
                      f"Portfolio heat: {self.portfolio_heat:.1%}")
        
        # Close remaining positions
        print("\nClosing remaining positions...")
        for symbol in list(self.positions.keys()):
            if symbol in all_prices:
                last_price = all_prices[symbol].iloc[-1]['close']
                self._close_position(symbol, last_price, all_timestamps[-1], 'end_of_test')
        
        # Calculate and display results
        self._calculate_performance()
        self._generate_report(signals_evaluated, signals_taken)
    
    def _open_position_enhanced(self, symbol: str, signal: dict, price: float, 
                               timestamp: pd.Timestamp, volatility: float, atr: float):
        """Open position with enhanced sizing."""
        
        # Calculate enhanced position size
        position_info = self.calculate_position_size_enhanced(
            symbol, signal['quality'], price, atr, volatility
        )
        
        # Check if we have enough margin
        total_margin = sum(p.get('margin_required', 0) for p in self.positions.values())
        if total_margin + position_info['margin_required'] > self.current_capital:
            return  # Not enough margin
        
        # Open position
        self.positions[symbol] = {
            'type': 'long' if signal['signal'] == 1 else 'short',
            'entry_time': timestamp,
            'entry_price': price,
            'units': position_info['units'],
            'notional_value': position_info['notional_value'],
            'margin_required': position_info['margin_required'],
            'stop_loss_pct': position_info['stop_loss_pct'],
            'take_profit_pct': position_info['take_profit_pct'],
            'signal_quality': signal['quality'],
            'symbol': symbol,
            'risk_amount': position_info['risk_amount'],
            'position_pct': position_info['position_pct']
        }


def main():
    """Run enhanced backtest."""
    
    # Set optimized environment variables
    os.environ['FOREX_MIN_POSITION_SIZE_4H'] = '5000'  # Lower minimum for better scaling
    os.environ['FOREX_MAX_POSITIONS_4H'] = '12'  # Allow more positions
    
    symbols = ['EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF']
    
    # Test period
    start_date = '2024-07-01'
    end_date = '2024-12-31'
    
    # Run enhanced backtest
    backtester = Enhanced4HBacktester(symbols, initial_capital=100000)
    backtester.run_backtest(start_date, end_date)
    
    # Save results
    if backtester.trades:
        import pandas as pd
        trades_df = pd.DataFrame(backtester.trades)
        trades_df.to_csv('output/enhanced_4h_trades.csv', index=False)
        
        with open('output/enhanced_4h_metrics.json', 'w') as f:
            json.dump(backtester.metrics, f, indent=2, default=str)
        
        print("\n✅ Results saved to:")
        print("  - output/enhanced_4h_trades.csv")
        print("  - output/enhanced_4h_metrics.json")

if __name__ == "__main__":
    main()