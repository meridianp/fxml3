#!/usr/bin/env python
"""Complete backtest using 100:1 leverage models with all symbols."""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
from datetime import datetime
import json
import joblib
import warnings
warnings.filterwarnings('ignore')

from scripts.create_100x_leverage_backtester import Leverage100XBacktester

class Leverage100XBacktesterWithModels(Leverage100XBacktester):
    """Enhanced backtester that uses the new 100:1 leverage models."""
    
    def __init__(self, symbols: list, initial_capital: float = 100000):
        super().__init__(symbols, initial_capital)
        
        # Load all models
        self.models = {}
        self.scalers = {}
        self.model_configs = {}
        
        for symbol in symbols:
            model_dir = Path(f'models/{symbol}_100x_leverage')
            if model_dir.exists():
                try:
                    # Load ensemble models
                    self.models[symbol] = {
                        'rf': joblib.load(model_dir / 'rf_model.pkl'),
                        'gb': joblib.load(model_dir / 'gb_model.pkl'),
                        'lr': joblib.load(model_dir / 'lr_model.pkl')
                    }
                    self.scalers[symbol] = joblib.load(model_dir / 'scaler.pkl')
                    
                    # Load config
                    with open(model_dir / 'config.json', 'r') as f:
                        self.model_configs[symbol] = json.load(f)
                    
                    print(f"✅ Loaded 100x leverage models for {symbol} (accuracy: {self.model_configs[symbol]['accuracy']:.1%})")
                except Exception as e:
                    print(f"❌ Failed to load models for {symbol}: {e}")
                    # Fall back to existing models
                    self._load_fallback_models(symbol)
            else:
                print(f"⚠️  No 100x leverage models for {symbol}, using fallback")
                self._load_fallback_models(symbol)
    
    def _load_fallback_models(self, symbol: str):
        """Load existing 4H models as fallback."""
        model_path = f'models/{symbol}/4h_model.pkl'
        scaler_path = f'models/{symbol}/4h_scaler.pkl'
        
        if Path(model_path).exists():
            self.models[symbol] = {'fallback': joblib.load(model_path)}
            self.scalers[symbol] = joblib.load(scaler_path)
            self.model_configs[symbol] = {'accuracy': 0.5, 'type': 'fallback'}
    
    def generate_signal(self, symbol: str, features: pd.Series) -> dict:
        """Generate trading signal using ensemble models."""
        
        if symbol not in self.models:
            return {'signal': 0, 'quality': 0, 'reason': 'no_model'}
        
        try:
            # Get required features
            if symbol in self.model_configs and 'features' in self.model_configs[symbol]:
                required_features = self.model_configs[symbol]['features']
            else:
                # Fallback features
                required_features = [f for f in features.index if f in self.scalers[symbol].feature_names_in_]
            
            # Prepare features
            X = features[required_features].values.reshape(1, -1)
            
            # Check for NaN
            if np.any(np.isnan(X)):
                return {'signal': 0, 'quality': 0, 'reason': 'nan_features'}
            
            # Scale features
            X_scaled = self.scalers[symbol].transform(X)
            
            # Get predictions from all models
            if 'fallback' in self.models[symbol]:
                # Use fallback model
                prediction = self.models[symbol]['fallback'].predict(X_scaled)[0]
                probabilities = self.models[symbol]['fallback'].predict_proba(X_scaled)[0]
                quality = np.max(probabilities)
            else:
                # Ensemble prediction
                predictions = []
                all_probabilities = []
                
                for model_name, model in self.models[symbol].items():
                    pred = model.predict(X_scaled)[0]
                    predictions.append(pred)
                    
                    # Get probabilities
                    proba = model.predict_proba(X_scaled)[0]
                    all_probabilities.append(proba)
                
                # Majority vote
                prediction = np.sign(np.sum(predictions))
                
                # Average probability as quality
                avg_proba = np.mean(all_probabilities, axis=0)
                quality = np.max(avg_proba)
            
            # Additional filters for 100:1 leverage
            
            # 1. Session filter - boost quality during best hours
            hour = features.get('hour', datetime.now().hour)
            if hour in [20, 8, 4, 0, 16]:  # Best hours from backtest
                quality *= 1.2
            
            # 2. Volatility filter - reduce size in extreme volatility
            volatility = features.get('volatility_12', 0.001)
            if volatility > 0.002:  # High volatility
                quality *= 0.8
            
            # 3. Trend alignment
            if 'trend_strength_20' in features:
                trend = features['trend_strength_20']
                if abs(trend) > 0.7:  # Strong trend
                    if (prediction == 1 and trend > 0) or (prediction == -1 and trend < 0):
                        quality *= 1.1  # Aligned with trend
                    else:
                        quality *= 0.9  # Against trend
            
            # Cap quality at 1.0
            quality = min(quality, 1.0)
            
            return {
                'signal': int(prediction),
                'quality': float(quality),
                'reason': 'ensemble_model',
                'models_agree': len(set(predictions)) == 1 if 'predictions' in locals() else True
            }
            
        except Exception as e:
            print(f"Error generating signal for {symbol}: {e}")
            return {'signal': 0, 'quality': 0, 'reason': 'error'}
    
    def run_comprehensive_backtest(self, start_date: str, end_date: str):
        """Run backtest with detailed analysis."""
        
        print("\n" + "="*80)
        print("100:1 LEVERAGE COMPREHENSIVE BACKTEST")
        print("="*80)
        print(f"Period: {start_date} to {end_date}")
        print(f"Initial Capital: ${self.initial_capital:,.2f}")
        print(f"Models: {'100x Leverage Optimized' if any('fallback' not in m for m in self.models.values()) else 'Mixed'}")
        print("="*80)
        
        # Run the backtest
        self.run_backtest(start_date, end_date)
        
        # Additional analysis
        if self.trades:
            self._analyze_model_performance()
            self._analyze_risk_metrics()
            self._analyze_optimal_parameters()
    
    def _analyze_model_performance(self):
        """Analyze performance by model predictions."""
        trades_df = pd.DataFrame(self.trades)
        
        print("\n\nMODEL PERFORMANCE ANALYSIS")
        print("="*60)
        
        # Performance by signal quality
        if 'signal_quality' in trades_df.columns:
            trades_df['quality_bucket'] = pd.cut(trades_df['signal_quality'], 
                                                bins=[0, 0.6, 0.7, 0.8, 1.0],
                                                labels=['Low', 'Medium', 'High', 'Very High'])
            
            print("\nPerformance by Signal Quality:")
            for bucket in ['Low', 'Medium', 'High', 'Very High']:
                bucket_trades = trades_df[trades_df['quality_bucket'] == bucket]
                if len(bucket_trades) > 0:
                    win_rate = (bucket_trades['pnl'] > 0).mean()
                    avg_pnl = bucket_trades['pnl'].mean()
                    print(f"  {bucket}: {len(bucket_trades)} trades, "
                          f"Win Rate: {win_rate:.1%}, Avg P&L: ${avg_pnl:.2f}")
    
    def _analyze_risk_metrics(self):
        """Analyze risk-adjusted performance metrics."""
        if not self.equity_curve:
            return
        
        print("\n\nRISK METRICS ANALYSIS")
        print("="*60)
        
        # Daily returns
        equity_series = pd.Series(self.equity_curve)
        daily_returns = equity_series.pct_change().dropna()
        
        # Risk metrics
        volatility = daily_returns.std() * np.sqrt(252/180)  # Annualized
        downside_returns = daily_returns[daily_returns < 0]
        downside_vol = downside_returns.std() * np.sqrt(252/180)
        
        # Sortino ratio (using 0% as minimum acceptable return)
        sortino = (self.metrics['total_return'] * 2) / downside_vol if downside_vol > 0 else 0
        
        # Calmar ratio
        calmar = (self.metrics['total_return'] * 2) / abs(self.metrics['max_drawdown']) if self.metrics['max_drawdown'] < 0 else 0
        
        print(f"Annualized Volatility: {volatility:.1%}")
        print(f"Downside Volatility: {downside_vol:.1%}")
        print(f"Sortino Ratio: {sortino:.2f}")
        print(f"Calmar Ratio: {calmar:.2f}")
        
        # Maximum consecutive losses
        if self.trades:
            trades_df = pd.DataFrame(self.trades)
            trades_df['is_loss'] = trades_df['pnl'] < 0
            max_consecutive_losses = trades_df['is_loss'].rolling(window=len(trades_df), min_periods=1).sum().max()
            print(f"\nMax Consecutive Losses: {int(max_consecutive_losses)}")
    
    def _analyze_optimal_parameters(self):
        """Suggest optimal parameters based on backtest."""
        print("\n\nOPTIMAL PARAMETERS SUGGESTION")
        print("="*60)
        
        trades_df = pd.DataFrame(self.trades)
        
        # Optimal position size
        if 'notional_value' in trades_df.columns and 'pnl' in trades_df.columns:
            # Group by position size buckets
            trades_df['size_bucket'] = pd.cut(trades_df['notional_value'], bins=5)
            size_performance = trades_df.groupby('size_bucket')['pnl'].agg(['mean', 'count', 'sum'])
            
            best_size_bucket = size_performance['sum'].idxmax()
            print(f"Optimal Position Size Range: {best_size_bucket}")
        
        # Optimal holding time
        if 'holding_hours' in trades_df.columns:
            trades_df['time_bucket'] = pd.cut(trades_df['holding_hours'], 
                                             bins=[0, 4, 8, 12, 24, 100],
                                             labels=['0-4h', '4-8h', '8-12h', '12-24h', '24h+'])
            
            time_performance = trades_df.groupby('time_bucket')['pnl'].agg(['mean', 'count', 'sum'])
            print("\nPerformance by Holding Time:")
            print(time_performance)
        
        # Suggest adjustments
        print("\n\nRECOMMENDED ADJUSTMENTS:")
        
        current_win_rate = self.metrics['win_rate']
        if current_win_rate < 0.25:
            print("- Increase signal quality threshold to 0.70")
            print("- Reduce position sizes by 20%")
        elif current_win_rate > 0.40:
            print("- Consider lowering quality threshold to 0.60")
            print("- Increase position sizes by 20%")
        
        if self.metrics['max_drawdown'] < -0.15:
            print("- Implement daily loss limit at 3%")
            print("- Reduce concurrent positions to 6")
        
        if self.metrics['profit_factor'] < 1.3:
            print("- Increase take profit to 2.5:1")
            print("- Focus on London session trading")


def main():
    """Run comprehensive backtest."""
    
    # First check if we have 100x models
    model_check = []
    for symbol in ['EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF']:
        if Path(f'models/{symbol}_100x_leverage').exists():
            model_check.append(f"✅ {symbol}")
        else:
            model_check.append(f"❌ {symbol}")
    
    print("Model Status:")
    for status in model_check:
        print(f"  {status}")
    
    if all('❌' in s for s in model_check):
        print("\n⚠️  No 100x leverage models found!")
        print("Please run: python scripts/train_100x_leverage_models.py")
        return
    
    # Run backtest
    symbols = ['EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF']
    
    # Test period (out of sample)
    start_date = '2024-09-01'
    end_date = '2024-12-31'
    
    # Initialize backtester
    backtester = Leverage100XBacktesterWithModels(symbols, initial_capital=100000)
    
    # Run comprehensive backtest
    backtester.run_comprehensive_backtest(start_date, end_date)
    
    # Save detailed results
    if backtester.trades:
        trades_df = pd.DataFrame(backtester.trades)
        trades_df.to_csv('output/leverage_100x_complete_trades.csv', index=False)
        
        # Enhanced metrics
        enhanced_metrics = backtester.metrics.copy()
        enhanced_metrics['test_period'] = f"{start_date} to {end_date}"
        enhanced_metrics['models_used'] = list(backtester.model_configs.keys())
        enhanced_metrics['average_model_accuracy'] = np.mean([
            config['accuracy'] for config in backtester.model_configs.values()
        ])
        
        with open('output/leverage_100x_complete_metrics.json', 'w') as f:
            json.dump(enhanced_metrics, f, indent=2, default=str)
        
        print("\n✅ Results saved to:")
        print("  - output/leverage_100x_complete_trades.csv")
        print("  - output/leverage_100x_complete_metrics.json")

if __name__ == "__main__":
    main()