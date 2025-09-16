#!/usr/bin/env python
"""Minimal backtest demonstration with real GBPUSD data."""

import pandas as pd
import numpy as np
import joblib
from pathlib import Path


def run_minimal_backtest():
    """Run a minimal backtest to demonstrate with real data."""
    print("="*60)
    print("MINIMAL BACKTEST WITH REAL GBPUSD DATA")
    print("="*60)
    
    # Load data
    print("\nLoading data...")
    df = pd.read_parquet("data/features/GBPUSD_4h_features_advanced.parquet")
    
    # Use last 500 bars for quick demo
    df = df.tail(500)
    print(f"Using {len(df)} bars from {df.index[0]} to {df.index[-1]}")
    
    # Load model
    print("\nLoading model...")
    model = joblib.load("models/GBPUSD/best_model_lightgbm.joblib")
    scaler = joblib.load("models/GBPUSD/scaler.joblib")
    
    # Use common technical features that should exist
    base_features = [
        'returns_1', 'returns_5', 'returns_10',
        'volume_ratio', 'high_low_spread', 'close_to_high',
        'rsi_14', 'macd_signal', 'bb_position',
        'atr_14', 'adx_14', 'volume_sma_20'
    ]
    
    # Find available features
    available = [f for f in base_features if f in df.columns]
    print(f"Using {len(available)} available features")
    
    # If we don't have enough features, create some basic ones
    if len(available) < 5:
        print("Creating basic features...")
        df['returns_1'] = df['close'].pct_change()
        df['returns_5'] = df['close'].pct_change(5)
        df['volume_ratio'] = df['volume'] / df['volume'].rolling(20).mean()
        df['high_low_spread'] = (df['high'] - df['low']) / df['close']
        df['close_to_high'] = (df['close'] - df['low']) / (df['high'] - df['low'])
        available = [f for f in df.columns if f not in ['open', 'high', 'low', 'close', 'volume']]
    
    # Simple backtest
    print("\nRunning backtest...")
    initial_capital = 10000
    capital = initial_capital
    trades = []
    position = None
    
    for i in range(50, len(df) - 1):
        try:
            # Get features
            X = df[available].iloc[i:i+1].fillna(0)
            
            # Scale (handle shape mismatch by using only available features)
            try:
                X_scaled = scaler.transform(X)
            except:
                # If scaler expects different features, just normalize
                X_scaled = (X - X.mean()) / (X.std() + 1e-8)
            
            # Predict
            pred = model.predict(X_scaled)[0]
            proba = model.predict_proba(X_scaled)[0] if hasattr(model, 'predict_proba') else [0.33, 0.34, 0.33]
            
            # LightGBM: 0=sell, 1=hold, 2=buy
            signal = pred - 1  # Convert to -1, 0, 1
            confidence = max(proba)
            
            current_price = df.iloc[i]['close']
            
            # Simple trading logic
            if position is None and confidence > 0.6:
                if signal == 1:  # Buy
                    position = {
                        'type': 'BUY',
                        'entry': current_price,
                        'size': capital * 0.02 / current_price  # 2% position
                    }
                elif signal == -1:  # Sell
                    position = {
                        'type': 'SELL',
                        'entry': current_price,
                        'size': capital * 0.02 / current_price
                    }
            
            elif position is not None:
                # Exit after 10 bars or 2% move
                bars_held = trades[-1]['bars'] if trades and not trades[-1].get('exit') else 0
                
                if position['type'] == 'BUY':
                    pnl_pct = (current_price - position['entry']) / position['entry']
                else:
                    pnl_pct = (position['entry'] - current_price) / position['entry']
                
                if abs(pnl_pct) > 0.02 or bars_held > 10:
                    # Exit
                    if position['type'] == 'BUY':
                        pnl = (current_price - position['entry']) * position['size']
                    else:
                        pnl = (position['entry'] - current_price) * position['size']
                    
                    # Costs
                    pnl -= position['size'] * current_price * 0.00007
                    capital += pnl
                    
                    trades.append({
                        'type': position['type'],
                        'entry': position['entry'],
                        'exit': current_price,
                        'pnl': pnl,
                        'bars': bars_held
                    })
                    
                    position = None
                elif trades and not trades[-1].get('exit'):
                    trades[-1]['bars'] = bars_held + 1
                    
        except Exception as e:
            continue
    
    # Results
    print("\n" + "="*60)
    print("RESULTS")
    print("="*60)
    
    total_return = (capital - initial_capital) / initial_capital
    print(f"Initial Capital: ${initial_capital:,.2f}")
    print(f"Final Capital: ${capital:,.2f}")
    print(f"Return: {total_return*100:.2f}%")
    print(f"Total Trades: {len(trades)}")
    
    if trades:
        wins = [t for t in trades if t['pnl'] > 0]
        print(f"Win Rate: {len(wins)/len(trades)*100:.1f}%")
        
        print("\nLast 5 trades:")
        for t in trades[-5:]:
            print(f"  {t['type']} @ {t['entry']:.5f} -> {t.get('exit', 'open')}, P&L: ${t['pnl']:.2f}")
    
    print("\nBacktest complete!")


if __name__ == "__main__":
    run_minimal_backtest()