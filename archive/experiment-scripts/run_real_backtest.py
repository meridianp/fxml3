#!/usr/bin/env python
"""Run a real backtest with actual market data."""

import sys
from pathlib import Path
from datetime import datetime
import pandas as pd
import numpy as np
import joblib
import json

# Add parent directory to path
sys.path.append(str(Path(__file__).parent))

from fxml4.backtesting.event_driven_engine import EventDrivenBacktester, Portfolio
from fxml4.backtesting.execution import ExecutionHandler, SimpleSlippageModel
from fxml4.backtesting.risk_management import (
    RiskManager, StopLossManager, DrawdownControl, PercentagePositionSizer
)
from fxml4.backtesting.performance_metrics import PerformanceAnalyzer
from fxml4.strategy.ml_signal_generator import MLSignalGenerator
from fxml4.strategy.integrated_strategy import IntegratedStrategy


def load_market_data(symbol: str, start_date: datetime, end_date: datetime) -> pd.DataFrame:
    """Load real market data from parquet files."""
    # Load the feature file which contains OHLCV data
    feature_file = Path(f"data/features/{symbol}_4h_features_advanced.parquet")
    
    if not feature_file.exists():
        raise FileNotFoundError(f"Data file not found: {feature_file}")
    
    # Load data
    df = pd.read_parquet(feature_file)
    
    # Filter by date range
    mask = (df.index >= start_date) & (df.index <= end_date)
    df = df.loc[mask]
    
    print(f"Loaded {len(df)} bars of {symbol} data from {df.index[0]} to {df.index[-1]}")
    
    return df


def run_backtest():
    """Run a real backtest with GBPUSD data."""
    print("="*80)
    print("RUNNING REAL BACKTEST WITH GBPUSD DATA")
    print("="*80)
    
    # Parameters
    symbol = "GBPUSD"
    start_date = datetime(2023, 1, 1)
    end_date = datetime(2024, 6, 30)  # 18 months
    initial_capital = 10000.0
    
    print(f"\nBacktest Parameters:")
    print(f"Symbol: {symbol}")
    print(f"Period: {start_date.date()} to {end_date.date()}")
    print(f"Initial Capital: ${initial_capital:,.2f}")
    
    # Load the trained model
    model_path = Path(f"models/{symbol}/best_model_lightgbm.joblib")
    scaler_path = Path(f"models/{symbol}/scaler.joblib")
    
    print(f"\nLoading model from {model_path}")
    model = joblib.load(model_path)
    scaler = joblib.load(scaler_path)
    
    # Load selected features
    with open(Path(f"models/{symbol}/selected_features.json"), 'r') as f:
        selected_features = json.load(f)
    
    print(f"Model uses {len(selected_features)} features")
    
    # Load market data
    market_data = load_market_data(symbol, start_date, end_date)
    
    # Create components
    print("\nSetting up backtest components...")
    
    # Position sizing - 2% risk per trade
    position_sizer = PercentagePositionSizer(percentage=0.02)
    
    # Stop loss manager - 2x ATR stop, 2:1 reward/risk
    stop_loss_manager = StopLossManager(
        stop_type="atr",
        stop_distance=2.0,
        take_profit_ratio=2.0,
        use_trailing=True,
        trailing_distance=1.5
    )
    
    # Drawdown control - 20% max drawdown
    drawdown_control = DrawdownControl(
        max_drawdown_pct=0.20,
        max_daily_loss_pct=0.05,
        max_weekly_loss_pct=0.10
    )
    
    # Risk manager
    risk_manager = RiskManager(
        position_sizer=position_sizer,
        stop_loss_manager=stop_loss_manager,
        drawdown_control=drawdown_control,
        max_positions=3,
        leverage_limit=2.0
    )
    
    # Execution handler with realistic costs
    execution_handler = ExecutionHandler(
        slippage_model=SimpleSlippageModel(slippage_pct=0.00005),  # 0.5 pips
        fee_pct=0.00002  # 0.2 pips commission
    )
    
    # ML Signal generator
    signal_generator = MLSignalGenerator(
        model=model,
        config={
            "threshold": 0.65,
            "probability_mode": True,
            "signal_cooldown": 14400,  # 4 hours
            "use_technical_features": True,
            "feature_columns": selected_features,
        }
    )
    
    # Create strategy
    strategy = IntegratedStrategy(
        signal_generators=[signal_generator],
        config={
            "signal_aggregation": "weighted",
            "min_combined_strength": 0.65,
        }
    )
    
    # Create portfolio
    portfolio = Portfolio(
        initial_capital=initial_capital,
        fee_model="percentage",
        risk_manager=risk_manager
    )
    
    print("\nRunning backtest...")
    print("This may take a few moments...")
    
    # Track progress
    trades = []
    equity_curve = []
    
    try:
        # Process data bar by bar (simplified backtest)
        current_position = None
        
        for i in range(100, len(market_data)):  # Need history for features
            # Get current bar
            current_bar = market_data.iloc[i]
            historical_data = market_data.iloc[:i+1]
            
            # Update portfolio with current price
            current_price = current_bar['close']
            
            # Generate features for the model
            features = historical_data[selected_features].iloc[-1:].copy()
            
            # Scale features
            features_scaled = scaler.transform(features)
            
            # Get prediction
            if hasattr(model, 'predict_proba'):
                # Adjust for LightGBM (classes 0,1,2 -> -1,0,1)
                proba = model.predict_proba(features_scaled)[0]
                # Get probability for buy (class 2 in LightGBM = 1 in our system)
                buy_prob = proba[2] if len(proba) > 2 else 0
                sell_prob = proba[0] if len(proba) > 0 else 0
            else:
                prediction = model.predict(features_scaled)[0]
                buy_prob = 1.0 if prediction == 2 else 0.0
                sell_prob = 1.0 if prediction == 0 else 0.0
            
            # Simple position management
            if current_position is None:
                # Check for entry signal
                if buy_prob > 0.65:
                    # Enter long position
                    position_size = initial_capital * 0.02 / current_price
                    current_position = {
                        'type': 'long',
                        'entry_price': current_price,
                        'size': position_size,
                        'entry_time': current_bar.name,
                        'stop_loss': current_price - (2.0 * current_bar.get('atr_14', 0.001)),
                        'take_profit': current_price + (4.0 * current_bar.get('atr_14', 0.001))
                    }
                elif sell_prob > 0.65:
                    # Enter short position
                    position_size = initial_capital * 0.02 / current_price
                    current_position = {
                        'type': 'short', 
                        'entry_price': current_price,
                        'size': position_size,
                        'entry_time': current_bar.name,
                        'stop_loss': current_price + (2.0 * current_bar.get('atr_14', 0.001)),
                        'take_profit': current_price - (4.0 * current_bar.get('atr_14', 0.001))
                    }
            else:
                # Check exit conditions
                exit_trade = False
                exit_reason = ""
                
                if current_position['type'] == 'long':
                    if current_price <= current_position['stop_loss']:
                        exit_trade = True
                        exit_reason = "stop_loss"
                    elif current_price >= current_position['take_profit']:
                        exit_trade = True
                        exit_reason = "take_profit"
                else:  # short
                    if current_price >= current_position['stop_loss']:
                        exit_trade = True
                        exit_reason = "stop_loss"
                    elif current_price <= current_position['take_profit']:
                        exit_trade = True
                        exit_reason = "take_profit"
                
                if exit_trade:
                    # Calculate P&L
                    if current_position['type'] == 'long':
                        pnl = (current_price - current_position['entry_price']) * current_position['size']
                    else:
                        pnl = (current_position['entry_price'] - current_price) * current_position['size']
                    
                    # Apply costs
                    costs = current_position['size'] * current_price * 0.00007  # Total costs
                    pnl -= costs
                    
                    trades.append({
                        'entry_time': current_position['entry_time'],
                        'exit_time': current_bar.name,
                        'type': current_position['type'],
                        'entry_price': current_position['entry_price'],
                        'exit_price': current_price,
                        'size': current_position['size'],
                        'pnl': pnl,
                        'exit_reason': exit_reason
                    })
                    
                    current_position = None
            
            # Track equity
            total_pnl = sum(t['pnl'] for t in trades)
            current_equity = initial_capital + total_pnl
            
            equity_curve.append({
                'time': current_bar.name,
                'equity': current_equity,
                'price': current_price
            })
            
            # Progress indicator
            if i % 500 == 0:
                print(f"Processed {i}/{len(market_data)} bars...")
        
        # Close any open position
        if current_position is not None:
            current_price = market_data.iloc[-1]['close']
            if current_position['type'] == 'long':
                pnl = (current_price - current_position['entry_price']) * current_position['size']
            else:
                pnl = (current_position['entry_price'] - current_price) * current_position['size']
            
            costs = current_position['size'] * current_price * 0.00007
            pnl -= costs
            
            trades.append({
                'entry_time': current_position['entry_time'],
                'exit_time': market_data.index[-1],
                'type': current_position['type'],
                'entry_price': current_position['entry_price'],
                'exit_price': current_price,
                'size': current_position['size'],
                'pnl': pnl,
                'exit_reason': 'end_of_data'
            })
        
        # Calculate final metrics
        print("\n" + "="*80)
        print("BACKTEST RESULTS")
        print("="*80)
        
        total_trades = len(trades)
        winning_trades = [t for t in trades if t['pnl'] > 0]
        losing_trades = [t for t in trades if t['pnl'] <= 0]
        
        total_pnl = sum(t['pnl'] for t in trades)
        final_equity = initial_capital + total_pnl
        total_return = (final_equity - initial_capital) / initial_capital
        
        print(f"\nPerformance Summary:")
        print(f"Initial Capital: ${initial_capital:,.2f}")
        print(f"Final Equity: ${final_equity:,.2f}")
        print(f"Total Return: {total_return*100:.2f}%")
        print(f"Total P&L: ${total_pnl:,.2f}")
        
        print(f"\nTrading Statistics:")
        print(f"Total Trades: {total_trades}")
        print(f"Winning Trades: {len(winning_trades)}")
        print(f"Losing Trades: {len(losing_trades)}")
        print(f"Win Rate: {len(winning_trades)/total_trades*100:.1f}%" if total_trades > 0 else "N/A")
        
        if winning_trades:
            avg_win = sum(t['pnl'] for t in winning_trades) / len(winning_trades)
            print(f"Average Win: ${avg_win:.2f}")
        
        if losing_trades:
            avg_loss = sum(t['pnl'] for t in losing_trades) / len(losing_trades)
            print(f"Average Loss: ${avg_loss:.2f}")
            
            if winning_trades:
                profit_factor = sum(t['pnl'] for t in winning_trades) / abs(sum(t['pnl'] for t in losing_trades))
                print(f"Profit Factor: {profit_factor:.2f}")
        
        # Calculate max drawdown
        equity_series = pd.Series([e['equity'] for e in equity_curve])
        running_max = equity_series.expanding().max()
        drawdown = (equity_series - running_max) / running_max
        max_drawdown = drawdown.min()
        
        print(f"\nRisk Metrics:")
        print(f"Maximum Drawdown: {max_drawdown*100:.2f}%")
        
        # Calculate Sharpe ratio (simplified)
        if len(equity_curve) > 1:
            returns = equity_series.pct_change().dropna()
            if len(returns) > 0 and returns.std() > 0:
                # Annualized Sharpe (4h bars, ~1460 per year)
                sharpe = returns.mean() / returns.std() * np.sqrt(1460)
                print(f"Sharpe Ratio: {sharpe:.2f}")
        
        # Show sample trades
        print(f"\nSample Trades (first 5):")
        print(f"{'Entry Time':<20} {'Type':<6} {'Entry':<8} {'Exit':<8} {'P&L':<10} {'Reason':<10}")
        print("-" * 70)
        
        for trade in trades[:5]:
            print(f"{str(trade['entry_time'])[:19]:<20} "
                  f"{trade['type']:<6} "
                  f"{trade['entry_price']:<8.5f} "
                  f"{trade['exit_price']:<8.5f} "
                  f"${trade['pnl']:<9.2f} "
                  f"{trade['exit_reason']:<10}")
        
        if len(trades) > 5:
            print(f"... and {len(trades) - 5} more trades")
        
        # Save results
        results = {
            'symbol': symbol,
            'start_date': str(start_date),
            'end_date': str(end_date),
            'initial_capital': initial_capital,
            'final_equity': final_equity,
            'total_return': total_return,
            'total_trades': total_trades,
            'win_rate': len(winning_trades)/total_trades if total_trades > 0 else 0,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe if 'sharpe' in locals() else 0,
            'trades': trades[:20]  # Save first 20 trades
        }
        
        output_file = Path("backtest_results_real.json")
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"\nResults saved to {output_file}")
        
    except Exception as e:
        print(f"\nError during backtest: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    run_backtest()