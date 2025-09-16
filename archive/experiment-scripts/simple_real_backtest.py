#!/usr/bin/env python
"""Simple real backtest with actual market data."""

import sys
from pathlib import Path
from datetime import datetime
import pandas as pd
import numpy as np
import joblib
import json

# Add parent directory to path
sys.path.append(str(Path(__file__).parent))


def run_simple_backtest():
    """Run a simple backtest with real GBPUSD data."""
    print("="*80)
    print("SIMPLE BACKTEST WITH REAL GBPUSD DATA")
    print("="*80)
    
    # Parameters
    symbol = "GBPUSD"
    start_date = datetime(2023, 1, 1)
    end_date = datetime(2024, 6, 30)
    initial_capital = 10000.0
    position_size_pct = 0.02  # 2% per trade
    
    print(f"\nBacktest Parameters:")
    print(f"Symbol: {symbol}")
    print(f"Period: {start_date.date()} to {end_date.date()}")
    print(f"Initial Capital: ${initial_capital:,.2f}")
    print(f"Position Size: {position_size_pct*100}% of capital")
    
    # Load market data
    feature_file = Path(f"data/features/{symbol}_4h_features_advanced.parquet")
    if not feature_file.exists():
        print(f"Error: Data file not found: {feature_file}")
        return
    
    print(f"\nLoading data from {feature_file}")
    df = pd.read_parquet(feature_file)
    
    # Filter by date
    mask = (df.index >= start_date) & (df.index <= end_date)
    df = df.loc[mask].copy()
    
    print(f"Loaded {len(df)} bars from {df.index[0]} to {df.index[-1]}")
    
    # Load model
    model_path = Path(f"models/{symbol}/best_model_lightgbm.joblib")
    scaler_path = Path(f"models/{symbol}/scaler.joblib")
    
    if not model_path.exists():
        print(f"Error: Model not found: {model_path}")
        return
    
    print(f"\nLoading model...")
    model = joblib.load(model_path)
    scaler = joblib.load(scaler_path)
    
    # Load features
    with open(Path(f"models/{symbol}/selected_features.json"), 'r') as f:
        selected_features = json.load(f)
    
    print(f"Model uses {len(selected_features)} features")
    
    # Simple backtest logic
    trades = []
    position = None
    equity = initial_capital
    equity_curve = []
    
    print("\nRunning backtest...")
    
    # Need at least 100 bars for indicators
    for i in range(100, len(df)):
        current_bar = df.iloc[i]
        current_time = df.index[i]
        current_price = current_bar['close']
        
        # Track equity
        equity_curve.append({
            'time': current_time,
            'equity': equity,
            'price': current_price
        })
        
        # Skip if we don't have all features
        if any(feat not in df.columns for feat in selected_features):
            missing = [f for f in selected_features if f not in df.columns]
            print(f"Warning: Missing features: {missing[:5]}...")
            break
        
        # Prepare features
        try:
            features = df[selected_features].iloc[i:i+1].copy()
            features_scaled = scaler.transform(features)
            
            # Get prediction (LightGBM uses 0,1,2 for classes -1,0,1)
            prediction = model.predict(features_scaled)[0]
            
            # Get probabilities if available
            if hasattr(model, 'predict_proba'):
                proba = model.predict_proba(features_scaled)[0]
                confidence = max(proba)
            else:
                confidence = 0.7  # Default confidence
            
            # Convert LightGBM classes to trading signals
            signal = prediction - 1  # 0,1,2 -> -1,0,1
            
        except Exception as e:
            continue
        
        # Position management
        if position is None and confidence > 0.65:
            # Enter position
            if signal == 1:  # Buy signal
                position = {
                    'type': 'long',
                    'entry_time': current_time,
                    'entry_price': current_price,
                    'size': (equity * position_size_pct) / current_price,
                    'confidence': confidence
                }
            elif signal == -1:  # Sell signal
                position = {
                    'type': 'short',
                    'entry_time': current_time,
                    'entry_price': current_price,
                    'size': (equity * position_size_pct) / current_price,
                    'confidence': confidence
                }
        
        elif position is not None:
            # Check exit conditions
            bars_held = i - df.index.get_loc(position['entry_time'])
            
            # Exit if opposite signal or held too long
            exit_position = False
            
            if position['type'] == 'long' and signal == -1:
                exit_position = True
            elif position['type'] == 'short' and signal == 1:
                exit_position = True
            elif bars_held > 20:  # Exit after 20 bars (80 hours)
                exit_position = True
            
            # Simple stop loss (2% loss)
            if position['type'] == 'long':
                pnl_pct = (current_price - position['entry_price']) / position['entry_price']
                if pnl_pct < -0.02:
                    exit_position = True
            else:
                pnl_pct = (position['entry_price'] - current_price) / position['entry_price']
                if pnl_pct < -0.02:
                    exit_position = True
            
            if exit_position:
                # Calculate P&L
                if position['type'] == 'long':
                    gross_pnl = (current_price - position['entry_price']) * position['size']
                else:
                    gross_pnl = (position['entry_price'] - current_price) * position['size']
                
                # Transaction costs (0.2 pips each way = 0.00004)
                costs = position['size'] * current_price * 0.00004
                net_pnl = gross_pnl - costs
                
                # Update equity
                equity += net_pnl
                
                # Record trade
                trades.append({
                    'entry_time': position['entry_time'],
                    'exit_time': current_time,
                    'type': position['type'],
                    'entry_price': position['entry_price'],
                    'exit_price': current_price,
                    'size': position['size'],
                    'gross_pnl': gross_pnl,
                    'costs': costs,
                    'net_pnl': net_pnl,
                    'confidence': position['confidence'],
                    'bars_held': bars_held
                })
                
                position = None
    
    # Results
    print("\n" + "="*80)
    print("BACKTEST RESULTS")
    print("="*80)
    
    total_return = (equity - initial_capital) / initial_capital
    
    print(f"\nPerformance Summary:")
    print(f"Initial Capital: ${initial_capital:,.2f}")
    print(f"Final Equity: ${equity:,.2f}")
    print(f"Total Return: {total_return*100:.2f}%")
    print(f"Total P&L: ${equity - initial_capital:,.2f}")
    
    if trades:
        winning_trades = [t for t in trades if t['net_pnl'] > 0]
        losing_trades = [t for t in trades if t['net_pnl'] <= 0]
        
        print(f"\nTrading Statistics:")
        print(f"Total Trades: {len(trades)}")
        print(f"Winning Trades: {len(winning_trades)}")
        print(f"Losing Trades: {len(losing_trades)}")
        print(f"Win Rate: {len(winning_trades)/len(trades)*100:.1f}%")
        
        if winning_trades:
            avg_win = sum(t['net_pnl'] for t in winning_trades) / len(winning_trades)
            print(f"Average Win: ${avg_win:.2f}")
        
        if losing_trades:
            avg_loss = sum(t['net_pnl'] for t in losing_trades) / len(losing_trades)
            print(f"Average Loss: ${avg_loss:.2f}")
            
            if winning_trades:
                profit_factor = sum(t['net_pnl'] for t in winning_trades) / abs(sum(t['net_pnl'] for t in losing_trades))
                print(f"Profit Factor: {profit_factor:.2f}")
        
        # Calculate max drawdown
        equity_series = pd.Series([e['equity'] for e in equity_curve])
        running_max = equity_series.expanding().max()
        drawdown = (equity_series - running_max) / running_max
        max_drawdown = drawdown.min()
        
        print(f"\nRisk Metrics:")
        print(f"Maximum Drawdown: {max_drawdown*100:.2f}%")
        
        # Sample trades
        print(f"\nFirst 5 Trades:")
        print(f"{'Entry':<19} {'Type':<5} {'Entry$':<7} {'Exit$':<7} {'P&L':<8} {'Bars':<5}")
        print("-" * 60)
        
        for trade in trades[:5]:
            print(f"{str(trade['entry_time'])[:19]} {trade['type']:<5} "
                  f"{trade['entry_price']:.5f} {trade['exit_price']:.5f} "
                  f"${trade['net_pnl']:>7.2f} {trade['bars_held']:>5}")
        
        # Monthly performance
        trade_df = pd.DataFrame(trades)
        trade_df['exit_time'] = pd.to_datetime(trade_df['exit_time'])
        monthly_pnl = trade_df.groupby(trade_df['exit_time'].dt.to_period('M'))['net_pnl'].sum()
        
        print(f"\nMonthly P&L:")
        for month, pnl in monthly_pnl.items():
            print(f"{month}: ${pnl:>8.2f}")
    else:
        print("\nNo trades executed!")
    
    print("\n" + "="*80)
    print("Backtest complete!")


if __name__ == "__main__":
    run_simple_backtest()