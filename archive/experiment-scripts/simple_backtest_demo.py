#!/usr/bin/env python
"""Simple demonstration backtest with real GBPUSD data."""

import pandas as pd
import numpy as np
import joblib
import json
from pathlib import Path
from datetime import datetime


def run_demo_backtest():
    """Run a simplified backtest demonstration."""
    print("="*80)
    print("BACKTEST DEMONSTRATION WITH REAL GBPUSD DATA")
    print("="*80)
    
    # Parameters
    symbol = "GBPUSD"
    initial_capital = 10000.0
    risk_per_trade = 0.02  # 2% risk per trade
    
    # Load data
    print("\n1. Loading Market Data...")
    data_file = Path(f"data/features/{symbol}_4h_features_advanced.parquet")
    
    try:
        df = pd.read_parquet(data_file)
        print(f"   ✓ Loaded {len(df)} bars of {symbol} data")
        print(f"   ✓ Date range: {df.index[0]} to {df.index[-1]}")
    except Exception as e:
        print(f"   ✗ Error loading data: {e}")
        return
    
    # Load model
    print("\n2. Loading Trading Model...")
    model_path = Path(f"models/{symbol}/best_model_lightgbm.joblib")
    scaler_path = Path(f"models/{symbol}/scaler.joblib")
    
    try:
        model = joblib.load(model_path)
        scaler = joblib.load(scaler_path)
        print("   ✓ Loaded LightGBM model and scaler")
        
        # Load features
        with open(Path(f"models/{symbol}/selected_features.json"), 'r') as f:
            features = json.load(f)
        print(f"   ✓ Model uses {len(features)} features")
    except Exception as e:
        print(f"   ✗ Error loading model: {e}")
        return
    
    # Select recent data for demo (last 6 months)
    print("\n3. Preparing Backtest Data...")
    df = df.tail(1000)  # Last 1000 bars (~6 months of 4h data)
    print(f"   ✓ Using data from {df.index[0]} to {df.index[-1]}")
    
    # Simple backtest
    print("\n4. Running Backtest...")
    print("   Position sizing: 2% risk per trade")
    print("   Stop loss: 2 x ATR")
    print("   Take profit: 2:1 risk/reward")
    print("   Transaction costs: 0.7 pips round trip")
    
    trades = []
    equity = initial_capital
    position = None
    
    # Check which features are available
    available_features = [f for f in features if f in df.columns]
    missing_features = [f for f in features if f not in df.columns]
    
    if missing_features:
        print(f"\n   ⚠ Warning: {len(missing_features)} features missing, using {len(available_features)} available features")
    
    # Process bars
    for i in range(100, len(df) - 1):  # Need history for indicators
        current_bar = df.iloc[i]
        current_price = current_bar['close']
        
        try:
            # Prepare features (use available ones)
            X = df[available_features].iloc[i:i+1]
            
            # Handle any NaN values
            if X.isnull().any().any():
                continue
            
            # Scale and predict
            X_scaled = scaler.transform(X)
            
            # Get prediction and probability
            prediction = model.predict(X_scaled)[0]
            proba = model.predict_proba(X_scaled)[0]
            
            # LightGBM uses 0,1,2 for classes -1,0,1
            signal = prediction - 1
            confidence = max(proba)
            
        except Exception as e:
            continue
        
        # Trading logic
        if position is None and confidence > 0.65:
            # Enter new position
            if signal == 1:  # Buy
                atr = current_bar.get('atr_14', current_price * 0.001)
                position = {
                    'type': 'BUY',
                    'entry_idx': i,
                    'entry_price': current_price,
                    'stop_loss': current_price - 2 * atr,
                    'take_profit': current_price + 4 * atr,  # 2:1 RR
                    'size': (equity * risk_per_trade) / (2 * atr)
                }
            elif signal == -1:  # Sell
                atr = current_bar.get('atr_14', current_price * 0.001)
                position = {
                    'type': 'SELL',
                    'entry_idx': i,
                    'entry_price': current_price,
                    'stop_loss': current_price + 2 * atr,
                    'take_profit': current_price - 4 * atr,
                    'size': (equity * risk_per_trade) / (2 * atr)
                }
        
        elif position is not None:
            # Check exit conditions
            exit_trade = False
            exit_price = current_price
            exit_reason = ""
            
            if position['type'] == 'BUY':
                if current_price <= position['stop_loss']:
                    exit_trade = True
                    exit_reason = "Stop Loss"
                elif current_price >= position['take_profit']:
                    exit_trade = True
                    exit_reason = "Take Profit"
            else:  # SELL
                if current_price >= position['stop_loss']:
                    exit_trade = True
                    exit_reason = "Stop Loss"
                elif current_price <= position['take_profit']:
                    exit_trade = True
                    exit_reason = "Take Profit"
            
            # Time exit (20 bars = 80 hours)
            if i - position['entry_idx'] > 20:
                exit_trade = True
                exit_reason = "Time Exit"
            
            if exit_trade:
                # Calculate P&L
                if position['type'] == 'BUY':
                    gross_pnl = (exit_price - position['entry_price']) * position['size']
                else:
                    gross_pnl = (position['entry_price'] - exit_price) * position['size']
                
                # Transaction costs (0.7 pips = 0.00007)
                costs = position['size'] * exit_price * 0.00007
                net_pnl = gross_pnl - costs
                
                # Update equity
                equity += net_pnl
                
                # Record trade
                trades.append({
                    'type': position['type'],
                    'entry_price': position['entry_price'],
                    'exit_price': exit_price,
                    'pnl': net_pnl,
                    'reason': exit_reason,
                    'bars_held': i - position['entry_idx']
                })
                
                position = None
    
    # Results
    print("\n5. Backtest Results:")
    print("   " + "-"*50)
    
    if not trades:
        print("   No trades executed during backtest period")
        return
    
    # Performance metrics
    total_pnl = sum(t['pnl'] for t in trades)
    total_return = (equity - initial_capital) / initial_capital
    winning_trades = [t for t in trades if t['pnl'] > 0]
    losing_trades = [t for t in trades if t['pnl'] < 0]
    
    print(f"   Initial Capital: ${initial_capital:,.2f}")
    print(f"   Final Equity: ${equity:,.2f}")
    print(f"   Net P&L: ${total_pnl:,.2f}")
    print(f"   Return: {total_return*100:.2f}%")
    
    print(f"\n   Total Trades: {len(trades)}")
    print(f"   Winning Trades: {len(winning_trades)} ({len(winning_trades)/len(trades)*100:.1f}%)")
    print(f"   Losing Trades: {len(losing_trades)} ({len(losing_trades)/len(trades)*100:.1f}%)")
    
    if winning_trades:
        avg_win = sum(t['pnl'] for t in winning_trades) / len(winning_trades)
        print(f"   Average Win: ${avg_win:.2f}")
    
    if losing_trades:
        avg_loss = sum(t['pnl'] for t in losing_trades) / len(losing_trades)
        print(f"   Average Loss: ${avg_loss:.2f}")
        
        if winning_trades:
            profit_factor = abs(sum(t['pnl'] for t in winning_trades) / sum(t['pnl'] for t in losing_trades))
            print(f"   Profit Factor: {profit_factor:.2f}")
    
    # Exit reasons
    print("\n   Exit Reasons:")
    reason_counts = {}
    for t in trades:
        reason = t['reason']
        reason_counts[reason] = reason_counts.get(reason, 0) + 1
    
    for reason, count in sorted(reason_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"   - {reason}: {count} ({count/len(trades)*100:.1f}%)")
    
    # Sample trades
    print("\n   Sample Trades (Last 5):")
    print("   Type  Entry    Exit     P&L      Reason")
    print("   " + "-"*45)
    
    for trade in trades[-5:]:
        print(f"   {trade['type']:<5} {trade['entry_price']:.5f} {trade['exit_price']:.5f} "
              f"${trade['pnl']:>7.2f}  {trade['reason']}")
    
    # Risk metrics
    if len(trades) > 1:
        # Simple drawdown calculation
        cumulative_pnl = []
        cum_sum = 0
        for t in trades:
            cum_sum += t['pnl']
            cumulative_pnl.append(initial_capital + cum_sum)
        
        peak = initial_capital
        max_dd = 0
        for value in cumulative_pnl:
            peak = max(peak, value)
            dd = (peak - value) / peak
            max_dd = max(max_dd, dd)
        
        print(f"\n   Maximum Drawdown: {max_dd*100:.2f}%")
        
        # Approximate Sharpe ratio
        returns = [t['pnl'] / initial_capital for t in trades]
        if len(returns) > 1:
            avg_return = np.mean(returns)
            std_return = np.std(returns)
            if std_return > 0:
                # Simplified annualization (4h bars, ~6 per day, ~250 trading days)
                sharpe = avg_return / std_return * np.sqrt(250 * 6 / len(trades))
                print(f"   Sharpe Ratio (approx): {sharpe:.2f}")
    
    print("\n" + "="*80)
    print("Backtest demonstration complete!")


if __name__ == "__main__":
    run_demo_backtest()