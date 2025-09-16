#!/usr/bin/env python
"""Real backtest with GBPUSD data using all features."""

import pandas as pd
import numpy as np
import joblib
from pathlib import Path
from datetime import datetime


def run_real_backtest():
    """Run a real backtest with proper feature handling."""
    print("="*80)
    print("REAL BACKTEST WITH GBPUSD DATA")
    print("="*80)
    
    # Load data
    df = pd.read_parquet("data/features/GBPUSD_4h_features_advanced.parquet")
    
    # Select recent data (2023-2024)
    df = df['2023-01-01':'2024-06-30']
    print(f"\nData period: {df.index[0]} to {df.index[-1]}")
    print(f"Total bars: {len(df)}")
    
    # Load model
    model = joblib.load("models/GBPUSD/best_model_lightgbm.joblib")
    scaler = joblib.load("models/GBPUSD/scaler.joblib")
    
    # Get feature columns (exclude OHLCV)
    exclude_cols = ['open', 'high', 'low', 'close', 'volume']
    feature_cols = [col for col in df.columns if col not in exclude_cols]
    print(f"\nUsing {len(feature_cols)} features for prediction")
    
    # Backtest parameters
    initial_capital = 10000.0
    position_size_pct = 0.02  # 2% risk per trade
    stop_loss_atr = 2.0  # 2x ATR stop loss
    take_profit_ratio = 2.0  # 2:1 reward/risk
    commission = 0.00007  # 0.7 pips round trip
    
    print("\nBacktest Configuration:")
    print(f"Initial Capital: ${initial_capital:,.2f}")
    print(f"Position Size: {position_size_pct*100}% of capital")
    print(f"Stop Loss: {stop_loss_atr}x ATR")
    print(f"Take Profit: {take_profit_ratio}:1 R/R")
    print(f"Commission: {commission*10000:.1f} pips round trip")
    
    # Initialize backtest
    trades = []
    equity = initial_capital
    equity_curve = [(df.index[0], equity)]
    position = None
    
    print("\nRunning backtest...")
    
    # Process each bar
    for i in range(100, len(df)):
        current_time = df.index[i]
        current_bar = df.iloc[i]
        current_price = current_bar['close']
        
        # Skip if missing data
        if df[feature_cols].iloc[i].isnull().any():
            continue
        
        # Prepare features
        X = df[feature_cols].iloc[i:i+1]
        X_scaled = scaler.transform(X)
        
        # Get prediction
        try:
            prediction = model.predict(X_scaled)[0]
            proba = model.predict_proba(X_scaled)[0] if hasattr(model, 'predict_proba') else None
            
            # Convert LightGBM output (0,1,2) to signal (-1,0,1)
            signal = prediction - 1
            confidence = max(proba) if proba is not None else 0.7
            
        except Exception as e:
            continue
        
        # Position management
        if position is None and confidence > 0.65:
            # Enter new position
            if signal == 1:  # Buy signal
                atr = current_bar.get('atr_14', current_price * 0.001)
                position = {
                    'type': 'LONG',
                    'entry_time': current_time,
                    'entry_price': current_price,
                    'stop_loss': current_price - stop_loss_atr * atr,
                    'take_profit': current_price + stop_loss_atr * take_profit_ratio * atr,
                    'size': (equity * position_size_pct) / (stop_loss_atr * atr),
                    'confidence': confidence
                }
                
            elif signal == -1:  # Sell signal
                atr = current_bar.get('atr_14', current_price * 0.001)
                position = {
                    'type': 'SHORT',
                    'entry_time': current_time,
                    'entry_price': current_price,
                    'stop_loss': current_price + stop_loss_atr * atr,
                    'take_profit': current_price - stop_loss_atr * take_profit_ratio * atr,
                    'size': (equity * position_size_pct) / (stop_loss_atr * atr),
                    'confidence': confidence
                }
        
        elif position is not None:
            # Check exit conditions
            exit_trade = False
            exit_reason = ""
            
            if position['type'] == 'LONG':
                if current_price <= position['stop_loss']:
                    exit_trade = True
                    exit_reason = "Stop Loss"
                elif current_price >= position['take_profit']:
                    exit_trade = True
                    exit_reason = "Take Profit"
            else:  # SHORT
                if current_price >= position['stop_loss']:
                    exit_trade = True
                    exit_reason = "Stop Loss"
                elif current_price <= position['take_profit']:
                    exit_trade = True
                    exit_reason = "Take Profit"
            
            if exit_trade:
                # Calculate P&L
                if position['type'] == 'LONG':
                    gross_pnl = (current_price - position['entry_price']) * position['size']
                else:
                    gross_pnl = (position['entry_price'] - current_price) * position['size']
                
                # Apply commission
                commission_cost = position['size'] * current_price * commission
                net_pnl = gross_pnl - commission_cost
                
                # Update equity
                equity += net_pnl
                equity_curve.append((current_time, equity))
                
                # Record trade
                trades.append({
                    'entry_time': position['entry_time'],
                    'exit_time': current_time,
                    'type': position['type'],
                    'entry_price': position['entry_price'],
                    'exit_price': current_price,
                    'size': position['size'],
                    'gross_pnl': gross_pnl,
                    'commission': commission_cost,
                    'net_pnl': net_pnl,
                    'exit_reason': exit_reason,
                    'confidence': position['confidence']
                })
                
                position = None
        
        # Update equity curve
        if i % 50 == 0:  # Every 50 bars
            equity_curve.append((current_time, equity))
    
    # Results
    print("\n" + "="*80)
    print("BACKTEST RESULTS")
    print("="*80)
    
    # Overall performance
    final_equity = equity
    total_return = (final_equity - initial_capital) / initial_capital
    
    print(f"\nOverall Performance:")
    print(f"Initial Capital: ${initial_capital:,.2f}")
    print(f"Final Equity: ${final_equity:,.2f}")
    print(f"Total Return: {total_return*100:.2f}%")
    print(f"Total P&L: ${final_equity - initial_capital:,.2f}")
    
    # Trade statistics
    if trades:
        winning_trades = [t for t in trades if t['net_pnl'] > 0]
        losing_trades = [t for t in trades if t['net_pnl'] <= 0]
        
        print(f"\nTrading Statistics:")
        print(f"Total Trades: {len(trades)}")
        print(f"Winning Trades: {len(winning_trades)} ({len(winning_trades)/len(trades)*100:.1f}%)")
        print(f"Losing Trades: {len(losing_trades)} ({len(losing_trades)/len(trades)*100:.1f}%)")
        
        if winning_trades:
            avg_win = sum(t['net_pnl'] for t in winning_trades) / len(winning_trades)
            max_win = max(t['net_pnl'] for t in winning_trades)
            print(f"Average Win: ${avg_win:.2f}")
            print(f"Largest Win: ${max_win:.2f}")
        
        if losing_trades:
            avg_loss = sum(t['net_pnl'] for t in losing_trades) / len(losing_trades)
            max_loss = min(t['net_pnl'] for t in losing_trades)
            print(f"Average Loss: ${avg_loss:.2f}")
            print(f"Largest Loss: ${max_loss:.2f}")
            
            if winning_trades:
                profit_factor = sum(t['net_pnl'] for t in winning_trades) / abs(sum(t['net_pnl'] for t in losing_trades))
                print(f"Profit Factor: {profit_factor:.2f}")
        
        # Commission analysis
        total_commission = sum(t['commission'] for t in trades)
        print(f"\nCost Analysis:")
        print(f"Total Commission Paid: ${total_commission:.2f}")
        print(f"Commission per Trade: ${total_commission/len(trades):.2f}")
        
        # Exit reason analysis
        exit_reasons = {}
        for t in trades:
            reason = t['exit_reason']
            exit_reasons[reason] = exit_reasons.get(reason, 0) + 1
        
        print(f"\nExit Analysis:")
        for reason, count in sorted(exit_reasons.items(), key=lambda x: x[1], reverse=True):
            pct = count / len(trades) * 100
            print(f"{reason}: {count} trades ({pct:.1f}%)")
        
        # Risk metrics
        equity_series = pd.Series([e[1] for e in equity_curve], index=[e[0] for e in equity_curve])
        returns = equity_series.pct_change().dropna()
        
        if len(returns) > 0:
            # Maximum drawdown
            running_max = equity_series.expanding().max()
            drawdown = (equity_series - running_max) / running_max
            max_drawdown = drawdown.min()
            
            # Sharpe ratio (simplified)
            if returns.std() > 0:
                sharpe = returns.mean() / returns.std() * np.sqrt(252 * 6)  # Annualized for 4h bars
            else:
                sharpe = 0
            
            print(f"\nRisk Metrics:")
            print(f"Maximum Drawdown: {max_drawdown*100:.2f}%")
            print(f"Sharpe Ratio: {sharpe:.2f}")
            
            # Calculate Sortino ratio
            downside_returns = returns[returns < 0]
            if len(downside_returns) > 0 and downside_returns.std() > 0:
                sortino = returns.mean() / downside_returns.std() * np.sqrt(252 * 6)
                print(f"Sortino Ratio: {sortino:.2f}")
        
        # Sample trades
        print(f"\nSample Trades (Last 10):")
        print(f"{'Entry Time':<20} {'Type':<6} {'Entry':<8} {'Exit':<8} {'P&L':<10} {'Reason':<12}")
        print("-" * 70)
        
        for trade in trades[-10:]:
            print(f"{str(trade['entry_time'])[:19]:<20} "
                  f"{trade['type']:<6} "
                  f"{trade['entry_price']:<8.5f} "
                  f"{trade['exit_price']:<8.5f} "
                  f"${trade['net_pnl']:<9.2f} "
                  f"{trade['exit_reason']:<12}")
        
        # Monthly breakdown
        trade_df = pd.DataFrame(trades)
        trade_df['exit_time'] = pd.to_datetime(trade_df['exit_time'])
        trade_df['month'] = trade_df['exit_time'].dt.to_period('M')
        
        monthly_pnl = trade_df.groupby('month')['net_pnl'].agg(['sum', 'count'])
        
        print(f"\nMonthly Performance:")
        print(f"{'Month':<10} {'P&L':<12} {'Trades':<8}")
        print("-" * 30)
        
        for month, row in monthly_pnl.iterrows():
            print(f"{str(month):<10} ${row['sum']:<11.2f} {int(row['count']):<8}")
        
        # Calculate annualized return
        days_in_backtest = (df.index[-1] - df.index[0]).days
        years = days_in_backtest / 365.25
        annualized_return = (final_equity / initial_capital) ** (1/years) - 1
        
        print(f"\nAnnualized Performance:")
        print(f"Backtest Period: {days_in_backtest} days ({years:.2f} years)")
        print(f"Annualized Return: {annualized_return*100:.2f}%")
        
    else:
        print("\nNo trades were executed during the backtest period.")
    
    print("\n" + "="*80)
    print("Backtest complete!")


if __name__ == "__main__":
    run_real_backtest()