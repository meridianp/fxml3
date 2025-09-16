#!/usr/bin/env python
"""Optimized 4-hour backtester with better position sizing."""

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
import warnings
warnings.filterwarnings('ignore')

load_dotenv()

class Optimized4HBacktester:
    """4-hour backtester with optimized position sizing and exits."""
    
    def __init__(self, symbols: list, initial_capital: float = 100000):
        self.symbols = symbols
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        
        # Optimized position sizing
        self.min_position_size = float(os.getenv('FOREX_MIN_POSITION_SIZE_4H', 10000))  # $10k default
        self.account_leverage = float(os.getenv('FOREX_ACCOUNT_LEVERAGE', 40))
        self.max_positions = int(os.getenv('FOREX_MAX_POSITIONS_4H', 10))  # Increased to 10
        self.max_risk_per_trade = float(os.getenv('FOREX_MAX_RISK_PER_TRADE', 0.01))  # 1%
        
        # 4-hour specific settings
        self.max_holding_hours = 48  # Max 2 days
        self.min_holding_hours = 4   # Min 1 bar
        self.signal_quality_threshold = 0.5  # Take signals with 50%+ quality
        
        # Load models
        self.models_dir = Path("models/h4_models")
        self.h4_data_dir = Path("data/h4_processed")
        self.models = {}
        self.features = {}
        self.load_models()
        
        # Trading state
        self.positions = {}
        self.trades = []
        self.equity_curve = [initial_capital]
        self.hourly_returns = []
        self.signal_history = []
        
        print("\nOptimized 4H Backtester initialized:")
        print(f"  Min Position Size: ${self.min_position_size:,.0f}")
        print(f"  Max Positions: {self.max_positions}")
        print(f"  Max Holding: {self.max_holding_hours} hours")
        print(f"  Signal Quality Threshold: {self.signal_quality_threshold:.0%}")
        
    def load_models(self):
        """Load 4-hour trained models."""
        for symbol in self.symbols:
            model_file = self.models_dir / f"{symbol}_h4_models.joblib"
            feature_file = self.models_dir / f"{symbol}_h4_features.json"
            
            if model_file.exists() and feature_file.exists():
                # Load model
                model_data = joblib.load(model_file)
                self.models[symbol] = model_data
                
                # Load features
                with open(feature_file, 'r') as f:
                    feature_data = json.load(f)
                self.features[symbol] = feature_data['features']
                
                # Get best model accuracy
                results = model_data.get('training_results', {})
                best_acc = max([r.get('test_signal_accuracy', 0) for r in results.values()])
                print(f"✅ Loaded {symbol} 4H model (accuracy: {best_acc:.1%})")
    
    def load_4h_data(self, symbol: str) -> pd.DataFrame:
        """Load preprocessed 4-hour data."""
        data_file = self.h4_data_dir / f"{symbol}_h4_features.parquet"
        if data_file.exists():
            return pd.read_parquet(data_file)
        return None
    
    def load_4h_price_data(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """Load raw price data and aggregate to 4-hour bars."""
        # Convert symbol format (EURUSD -> C_EURUSD)
        raw_symbol = f"C_{symbol}"
        
        # Load minute data from raw Polygon data
        data_path = Path(f"input/{raw_symbol}")
        
        if not data_path.exists():
            print(f"Data path not found: {data_path}")
            return None
        
        # Parse dates
        start = pd.to_datetime(start_date)
        end = pd.to_datetime(end_date)
        
        all_data = []
        
        # Iterate through year/month/day structure
        for year_dir in sorted(data_path.glob("year=*")):
            year = int(year_dir.name.split("=")[1])
            
            for month_dir in sorted(year_dir.glob("month=*")):
                month = int(month_dir.name.split("=")[1])
                
                # Skip if outside date range
                month_start = pd.Timestamp(year, month, 1)
                month_end = month_start + pd.DateOffset(months=1) - pd.DateOffset(days=1)
                
                if month_end < start or month_start > end:
                    continue
                
                for day_dir in sorted(month_dir.glob("day=*")):
                    day = int(day_dir.name.split("=")[1])
                    
                    # Skip if outside date range
                    day_date = pd.Timestamp(year, month, day)
                    if day_date < start or day_date > end:
                        continue
                    
                    # Load parquet files for this day
                    for parquet_file in day_dir.glob("*.parquet*"):  # Match .parquet and .parquet.gz
                        try:
                            df = pd.read_parquet(parquet_file)
                            if not df.empty:
                                all_data.append(df)
                        except Exception as e:
                            print(f"Error reading {parquet_file}: {e}")
        
        if not all_data:
            return None
        
        # Combine all data
        combined = pd.concat(all_data, ignore_index=True)
        
        # Convert timestamp to datetime and set as index
        combined['timestamp'] = pd.to_datetime(combined['timestamp'])
        combined = combined.set_index('timestamp').sort_index()
        
        # Aggregate to 4-hour bars
        h4_data = combined.resample('4H', label='right', closed='right').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }).dropna()
        
        # Remove timezone to match feature data
        h4_data.index = h4_data.index.tz_localize(None)
        
        return h4_data
    
    def generate_signal(self, symbol: str, features: pd.Series) -> dict:
        """Generate trading signal from 4H model."""
        if symbol not in self.models:
            return {'signal': 0, 'confidence': 0, 'quality': 0}
        
        model_data = self.models[symbol]
        model = model_data['models'].get('ensemble')
        scaler = model_data['scalers'].get('ensemble')
        
        if model is None:
            return {'signal': 0, 'confidence': 0, 'quality': 0}
        
        # Prepare features
        feature_names = self.features[symbol]
        X = features[feature_names].values.reshape(1, -1)
        
        # Scale if needed
        if scaler is not None:
            X = scaler.transform(X)
        
        # Predict based on model type
        if hasattr(model, 'predict'):
            if type(model).__name__ == 'Booster':
                if 'xgb' in str(type(model)):
                    import xgboost as xgb
                    dmatrix = xgb.DMatrix(X, feature_names=feature_names)
                    prediction = model.predict(dmatrix)[0]
                else:  # LightGBM
                    prediction = model.predict(X)[0]
            else:
                prediction = model.predict(X)[0]
        else:
            prediction = 0
        
        # Generate signal with 4H-appropriate threshold
        threshold = 0.00005  # 0.5 basis points for 4H
        
        if prediction > threshold:
            signal = 1
        elif prediction < -threshold:
            signal = -1
        else:
            signal = 0
        
        # Calculate confidence and quality
        confidence = min(abs(prediction) * 50000, 100)  # Scale for 4H predictions
        
        # Quality score based on multiple factors
        quality_factors = []
        
        # 1. Prediction magnitude (scale for 4H predictions)
        # 0.00005 = 0.5 basis points = baseline
        # 0.0001 = 1 basis point = good
        # 0.0002 = 2 basis points = excellent
        pred_magnitude = abs(prediction)
        if pred_magnitude >= 0.0002:
            quality_factors.append(1.0)
        elif pred_magnitude >= 0.0001:
            quality_factors.append(0.8)
        elif pred_magnitude >= 0.00005:
            quality_factors.append(0.6)
        else:
            quality_factors.append(0.4)
        
        # 2. Volatility regime (prefer normal volatility)
        if 'volatility_12' in features:
            vol = features['volatility_12']
            if 0.001 < vol < 0.01:  # Normal range for 4H forex
                quality_factors.append(0.8)
            elif vol < 0.0005:  # Too low volatility
                quality_factors.append(0.4)
            else:  # High volatility
                quality_factors.append(0.6)
        else:
            quality_factors.append(0.5)
        
        # 3. Session quality (prefer active sessions)
        session_score = 0.5  # Default
        if 'session_London2' in features and features.get('session_London2', 0) == 1:
            session_score = 0.9  # London afternoon - best
        elif 'session_NewYork1' in features and features.get('session_NewYork1', 0) == 1:
            session_score = 0.8  # NY morning - good
        elif 'session_London1' in features and features.get('session_London1', 0) == 1:
            session_score = 0.7  # London morning - decent
        quality_factors.append(session_score)
        
        quality = np.mean(quality_factors)
        
        return {
            'signal': signal,
            'confidence': confidence,
            'quality': quality,
            'prediction': float(prediction)
        }
    
    def should_exit_position(self, position: dict, current_bar: pd.Series,
                           current_price: float, current_time: pd.Timestamp) -> tuple:
        """Check if position should be exited."""
        
        # Time-based exit
        hours_held = (current_time - position['entry_time']).total_seconds() / 3600
        if hours_held >= self.max_holding_hours:
            return True, 'max_time'
        
        # Stop loss
        if position['type'] == 'long':
            pnl_pct = (current_price - position['entry_price']) / position['entry_price']
        else:
            pnl_pct = (position['entry_price'] - current_price) / position['entry_price']
        
        if pnl_pct <= -position['stop_loss_pct']:
            return True, 'stop_loss'
        
        # Take profit (dynamic based on volatility)
        if pnl_pct >= position['take_profit_pct']:
            return True, 'take_profit'
        
        # Minimum holding period
        if hours_held < self.min_holding_hours:
            return False, None
        
        # Exit on opposite signal with quality
        new_signal = self.generate_signal(position['symbol'], current_bar)
        if new_signal['quality'] > self.signal_quality_threshold:
            if (position['type'] == 'long' and new_signal['signal'] == -1) or \
               (position['type'] == 'short' and new_signal['signal'] == 1):
                return True, 'signal_reversal'
        
        return False, None
    
    def calculate_position_size(self, symbol: str, signal_quality: float, 
                              volatility: float) -> dict:
        """Calculate position size with quality-based scaling."""
        
        # Base position size
        base_size = self.min_position_size
        
        # Scale by signal quality (0.5x to 1.5x)
        quality_multiplier = 0.5 + signal_quality
        
        # Scale by volatility (inverse relationship)
        if volatility > 0:
            vol_multiplier = min(0.01 / volatility, 1.5)  # Lower size for high vol
        else:
            vol_multiplier = 1.0
        
        # Scale by number of open positions
        position_multiplier = 1.0 - (len(self.positions) / self.max_positions) * 0.3
        
        # Final position size
        position_size = base_size * quality_multiplier * vol_multiplier * position_multiplier
        position_size = max(self.min_position_size, min(position_size, self.min_position_size * 3))
        
        # Calculate margin and risk
        margin_required = position_size / self.account_leverage
        
        # Dynamic stop loss based on volatility
        stop_loss_pct = min(max(volatility * 2, 0.001), 0.01)  # 0.1% to 1%
        take_profit_pct = stop_loss_pct * 2  # 2:1 reward/risk
        
        return {
            'units': position_size / 1,  # Simplified for now
            'notional_value': position_size,
            'margin_required': margin_required,
            'stop_loss_pct': stop_loss_pct,
            'take_profit_pct': take_profit_pct
        }
    
    def run_backtest(self, start_date: str, end_date: str):
        """Run 4-hour backtest with optimized execution."""
        print("\n" + "="*80)
        print("OPTIMIZED 4-HOUR FOREX BACKTEST")
        print("="*80)
        print(f"Period: {start_date} to {end_date}")
        print(f"Initial Capital: ${self.initial_capital:,.2f}")
        
        # Load all data - both features and prices
        all_data = {}
        all_prices = {}
        
        for symbol in self.symbols:
            # Load preprocessed features
            df_features = self.load_4h_data(symbol)
            
            # Load raw price data
            df_prices = self.load_4h_price_data(symbol, start_date, end_date)
            
            if df_features is not None and df_prices is not None:
                # Filter date range for features
                df_features = df_features[(df_features.index >= start_date) & (df_features.index <= end_date)]
                
                # Align the two datasets by index
                common_index = df_features.index.intersection(df_prices.index)
                
                if len(common_index) > 0:
                    all_data[symbol] = df_features.loc[common_index]
                    all_prices[symbol] = df_prices.loc[common_index]
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
            
            # First, check exits for existing positions
            for symbol in list(self.positions.keys()):
                if symbol in all_data and timestamp in all_data[symbol].index:
                    position = self.positions[symbol]
                    current_bar = all_data[symbol].loc[timestamp]
                    current_price = all_prices[symbol].loc[timestamp, 'close']
                    
                    should_exit, exit_reason = self.should_exit_position(
                        position, current_bar, current_price, timestamp
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
                                'bar': current_bar
                            })
            
            # Sort by quality and take best signals up to position limit
            signal_candidates.sort(key=lambda x: x['signal']['quality'], reverse=True)
            
            positions_to_open = min(
                len(signal_candidates),
                self.max_positions - len(self.positions)
            )
            
            for j in range(positions_to_open):
                candidate = signal_candidates[j]
                
                # Quality filter
                if candidate['signal']['quality'] >= self.signal_quality_threshold:
                    signals_taken += 1
                    self._open_position(
                        candidate['symbol'],
                        candidate['signal'],
                        candidate['price'],
                        timestamp,
                        candidate['volatility']
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
                      f"Signal efficiency: {signals_taken/max(signals_evaluated,1):.1%}")
        
        # Close remaining positions
        print("\nClosing remaining positions...")
        for symbol in list(self.positions.keys()):
            if symbol in all_prices:
                last_price = all_prices[symbol].iloc[-1]['close']
                self._close_position(symbol, last_price, all_timestamps[-1], 'end_of_test')
        
        # Calculate and display results
        self._calculate_performance()
        self._generate_report(signals_evaluated, signals_taken)
    
    def _open_position(self, symbol: str, signal: dict, price: float, 
                      timestamp: pd.Timestamp, volatility: float):
        """Open a new position."""
        
        # Calculate position size
        position_info = self.calculate_position_size(symbol, signal['quality'], volatility)
        
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
            'symbol': symbol
        }
    
    def _close_position(self, symbol: str, price: float, timestamp: pd.Timestamp, reason: str):
        """Close an existing position."""
        position = self.positions[symbol]
        
        # Calculate P&L
        if position['type'] == 'long':
            pnl = position['units'] * (price - position['entry_price'])
            pnl_pct = (price - position['entry_price']) / position['entry_price']
        else:
            pnl = position['units'] * (position['entry_price'] - price)
            pnl_pct = (position['entry_price'] - price) / position['entry_price']
        
        # Update capital
        self.current_capital += pnl
        
        # Record trade
        holding_hours = (timestamp - position['entry_time']).total_seconds() / 3600
        
        self.trades.append({
            'symbol': symbol,
            'type': position['type'],
            'entry_time': position['entry_time'],
            'entry_price': position['entry_price'],
            'exit_time': timestamp,
            'exit_price': price,
            'units': position['units'],
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'holding_hours': holding_hours,
            'exit_reason': reason,
            'signal_quality': position['signal_quality']
        })
        
        # Remove position
        del self.positions[symbol]
    
    def _update_equity(self, all_data: dict, all_prices: dict, timestamp: pd.Timestamp):
        """Update equity curve with unrealized P&L."""
        equity = self.current_capital
        
        for symbol, position in self.positions.items():
            if symbol in all_prices and timestamp in all_prices[symbol].index:
                current_price = all_prices[symbol].loc[timestamp, 'close']
                
                if position['type'] == 'long':
                    unrealized_pnl = position['units'] * (current_price - position['entry_price'])
                else:
                    unrealized_pnl = position['units'] * (position['entry_price'] - current_price)
                
                equity += unrealized_pnl
        
        self.equity_curve.append(equity)
    
    def _calculate_performance(self):
        """Calculate performance metrics."""
        if len(self.trades) == 0:
            self.metrics = {'error': 'No trades executed'}
            return
        
        trades_df = pd.DataFrame(self.trades)
        
        # Basic metrics
        total_trades = len(trades_df)
        winning_trades = trades_df[trades_df['pnl'] > 0]
        losing_trades = trades_df[trades_df['pnl'] < 0]
        
        win_rate = len(winning_trades) / total_trades
        avg_win = winning_trades['pnl'].mean() if len(winning_trades) > 0 else 0
        avg_loss = losing_trades['pnl'].mean() if len(losing_trades) > 0 else 0
        
        # Return metrics
        total_return = (self.current_capital - self.initial_capital) / self.initial_capital
        
        # Risk metrics
        equity_array = np.array(self.equity_curve)
        returns = np.diff(equity_array) / equity_array[:-1]
        
        if len(returns) > 0:
            sharpe_4h = np.mean(returns) / np.std(returns) if np.std(returns) > 0 else 0
            sharpe_annual = sharpe_4h * np.sqrt(6 * 252)  # Annualized from 4H
            
            # Max drawdown
            running_max = np.maximum.accumulate(equity_array)
            drawdown = (equity_array - running_max) / running_max
            max_drawdown = drawdown.min()
        else:
            sharpe_annual = 0
            max_drawdown = 0
        
        # Trading frequency
        avg_holding_hours = trades_df['holding_hours'].mean()
        trades_per_day = total_trades / (len(self.equity_curve) / 6) if len(self.equity_curve) > 6 else 0
        
        # Exit reason analysis
        exit_reasons = trades_df['exit_reason'].value_counts()
        
        self.metrics = {
            'total_trades': total_trades,
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': abs(avg_win * len(winning_trades) / (avg_loss * len(losing_trades))) if avg_loss != 0 else 0,
            'total_return': total_return,
            'sharpe_ratio': sharpe_annual,
            'max_drawdown': max_drawdown,
            'avg_holding_hours': avg_holding_hours,
            'trades_per_day': trades_per_day,
            'exit_reasons': exit_reasons.to_dict()
        }
    
    def _generate_report(self, signals_evaluated: int, signals_taken: int):
        """Generate performance report."""
        print("\n" + "="*80)
        print("BACKTEST RESULTS")
        print("="*80)
        
        if 'error' in self.metrics:
            print(f"❌ {self.metrics['error']}")
            return
        
        m = self.metrics
        
        print(f"\nPerformance Summary:")
        print(f"  Initial Capital:     ${self.initial_capital:,.2f}")
        print(f"  Final Capital:       ${self.current_capital:,.2f}")
        print(f"  Total Return:        {m['total_return']:+.2%}")
        print(f"  Sharpe Ratio:        {m['sharpe_ratio']:.2f}")
        print(f"  Max Drawdown:        {m['max_drawdown']:.2%}")
        
        print(f"\nTrading Statistics:")
        print(f"  Total Trades:        {m['total_trades']}")
        print(f"  Win Rate:            {m['win_rate']:.1%}")
        print(f"  Profit Factor:       {m['profit_factor']:.2f}")
        print(f"  Avg Holding:         {m['avg_holding_hours']:.1f} hours")
        print(f"  Trades per Day:      {m['trades_per_day']:.1f}")
        
        print(f"\nSignal Efficiency:")
        print(f"  Signals Evaluated:   {signals_evaluated}")
        print(f"  Signals Taken:       {signals_taken}")
        print(f"  Efficiency:          {signals_taken/max(signals_evaluated,1):.1%}")
        
        print(f"\nExit Reasons:")
        for reason, count in m['exit_reasons'].items():
            print(f"  {reason:20s} {count:4d} ({count/m['total_trades']:.1%})")
        
        # Per symbol performance
        if len(self.trades) > 0:
            trades_df = pd.DataFrame(self.trades)
            print(f"\nPer Symbol Performance:")
            for symbol in self.symbols:
                symbol_trades = trades_df[trades_df['symbol'] == symbol]
                if len(symbol_trades) > 0:
                    symbol_pnl = symbol_trades['pnl'].sum()
                    symbol_win_rate = (symbol_trades['pnl'] > 0).mean()
                    print(f"  {symbol}: {len(symbol_trades)} trades, "
                          f"Win rate: {symbol_win_rate:.1%}, "
                          f"P&L: ${symbol_pnl:,.2f}")


def main():
    """Run optimized 4H backtest."""
    
    # Update environment for 4H settings
    os.environ['FOREX_MIN_POSITION_SIZE_4H'] = '10000'  # $10k
    os.environ['FOREX_MAX_POSITIONS_4H'] = '10'  # Allow 10 positions
    
    symbols = ['EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF']
    
    # Test period - last 2 years
    end_date = '2024-12-31'
    start_date = '2023-01-01'
    
    # Run backtest
    backtester = Optimized4HBacktester(symbols, initial_capital=100000)
    backtester.run_backtest(start_date, end_date)


if __name__ == "__main__":
    main()